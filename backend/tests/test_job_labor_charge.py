"""Labour billing follows the Sri Lankan model.

Technicians are on monthly salaries, so an hourly rate is neither what they
earn nor what the customer pays. Labour is billed as one flat charge per job
(``Job.labor_cost``); ``JobLaborEntry`` exists to track *time* for utilisation
insight, not money.
"""

from datetime import datetime, timezone


def _owner_token(client, platform_admin, email="owner-charge@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _technician_id(client, token, email="tech-charge@example.com"):
    return client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _job(client, token):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=h,
    ).json()["id"]
    return client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake service"},
        headers=h,
    ).json()["id"]


START = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


# --- time tracking without a rate -------------------------------------------


def test_labor_entry_can_be_recorded_without_an_hourly_rate(client, platform_admin):
    """Starting a timer must not require a rate — that's the whole point."""
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token)
    job_id = _job(client, token)

    response = client.post(
        f"/api/v1/jobs/{job_id}/labor-entries",
        json={"technician_id": tech_id, "start_time": START.isoformat()},
        headers=h,
    )

    assert response.status_code == 201
    assert response.json()["hourly_rate"] is None
    assert response.json()["end_time"] is None


def test_hourly_rate_is_still_accepted_when_supplied(client, platform_admin):
    """Kept for any shop that genuinely pays hourly."""
    token = _owner_token(client, platform_admin, email="owner-charge-rate@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-charge-rate@example.com")
    job_id = _job(client, token)

    response = client.post(
        f"/api/v1/jobs/{job_id}/labor-entries",
        json={"technician_id": tech_id, "start_time": START.isoformat(), "hourly_rate": 800.0},
        headers=h,
    )

    assert response.status_code == 201
    assert response.json()["hourly_rate"] == 800.0


def test_negative_hourly_rate_is_rejected(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-charge-neg@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-charge-neg@example.com")
    job_id = _job(client, token)

    response = client.post(
        f"/api/v1/jobs/{job_id}/labor-entries",
        json={"technician_id": tech_id, "start_time": START.isoformat(), "hourly_rate": -1},
        headers=h,
    )

    assert response.status_code == 422


# --- the flat labour charge --------------------------------------------------


def test_labor_charge_defaults_to_zero_and_can_be_set(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-charge-set@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)

    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["labor_cost"] == 0.0

    response = client.patch(f"/api/v1/jobs/{job_id}", json={"labor_cost": 3500.0}, headers=h)

    assert response.status_code == 200
    assert response.json()["labor_cost"] == 3500.0


def test_negative_labor_charge_is_rejected(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-charge-negcost@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)

    response = client.patch(f"/api/v1/jobs/{job_id}", json={"labor_cost": -100.0}, headers=h)

    assert response.status_code == 422


def test_labor_charge_cannot_change_once_invoiced(client, db_session, platform_admin):
    """An issued invoice must not disagree with the job it came from.

    Invoicing isn't merged yet and the status machine blocks reaching
    `invoiced` manually, so the status is set directly. The guard has to exist
    before invoicing ships, not after.
    """
    from app.models.job import Job, JobStatus

    token = _owner_token(client, platform_admin, email="owner-charge-locked@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    client.patch(f"/api/v1/jobs/{job_id}", json={"labor_cost": 3500.0}, headers=h)

    db_session.query(Job).filter(Job.id == job_id).one().status = JobStatus.invoiced
    db_session.commit()

    response = client.patch(f"/api/v1/jobs/{job_id}", json={"labor_cost": 9999.0}, headers=h)

    assert response.status_code == 400
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["labor_cost"] == 3500.0


def test_other_fields_remain_editable_on_an_invoiced_job(client, db_session, platform_admin):
    """Only money is frozen — correcting a typo in the title stays fine."""
    from app.models.job import Job, JobStatus

    token = _owner_token(client, platform_admin, email="owner-charge-title@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)

    db_session.query(Job).filter(Job.id == job_id).one().status = JobStatus.invoiced
    db_session.commit()

    response = client.patch(f"/api/v1/jobs/{job_id}", json={"title": "Brake service (front)"}, headers=h)

    assert response.status_code == 200
    assert response.json()["title"] == "Brake service (front)"
