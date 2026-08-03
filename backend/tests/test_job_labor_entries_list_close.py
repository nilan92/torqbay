from datetime import datetime, timedelta, timezone


def _owner_token(client, platform_admin, email="owner-labor2@example.com", password="ownerpass123"):
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


def _technician_id(client, token, email="tech-labor2@example.com"):
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


def _open_entry(client, token, job_id, technician_id, rate=1500.0):
    """Start a timer: an entry with no end_time yet."""
    return client.post(
        f"/api/v1/jobs/{job_id}/labor-entries",
        json={
            "technician_id": technician_id,
            "start_time": START.isoformat(),
            "hourly_rate": rate,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


# --- listing ---------------------------------------------------------------


def test_labor_entries_can_be_listed_for_a_job(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token)
    job_id = _job(client, token)
    _open_entry(client, token, job_id, tech_id)

    response = client.get(f"/api/v1/jobs/{job_id}/labor-entries", headers=h)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["items"][0]["technician_id"] == tech_id
    assert body["items"][0]["end_time"] is None


def test_listing_returns_only_that_jobs_entries(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor2-scope@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-labor2-scope@example.com")
    job_a = _job(client, token)
    job_b = _job(client, token)
    _open_entry(client, token, job_a, tech_id, rate=1000.0)
    _open_entry(client, token, job_b, tech_id, rate=2000.0)

    body = client.get(f"/api/v1/jobs/{job_a}/labor-entries", headers=h).json()

    assert body["total"] == 1
    assert body["items"][0]["hourly_rate"] == 1000.0


def test_listing_another_tenants_job_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-labor2-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-labor2-b@example.com")
    job_id = _job(client, token_a)

    response = client.get(
        f"/api/v1/jobs/{job_id}/labor-entries", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response.status_code == 404


# --- closing an entry (stopping the timer) ---------------------------------


def test_closing_an_open_entry_sets_end_time(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor2-close@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-labor2-close@example.com")
    job_id = _job(client, token)
    entry_id = _open_entry(client, token, job_id, tech_id).json()["id"]

    end = (START + timedelta(hours=2, minutes=30)).isoformat()
    response = client.patch(
        f"/api/v1/jobs/{job_id}/labor-entries/{entry_id}",
        json={"end_time": end},
        headers=h,
    )

    assert response.status_code == 200
    assert response.json()["end_time"] is not None
    assert response.json()["id"] == entry_id


def test_end_time_before_start_time_is_rejected(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor2-before@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-labor2-before@example.com")
    job_id = _job(client, token)
    entry_id = _open_entry(client, token, job_id, tech_id).json()["id"]

    response = client.patch(
        f"/api/v1/jobs/{job_id}/labor-entries/{entry_id}",
        json={"end_time": (START - timedelta(hours=1)).isoformat()},
        headers=h,
    )

    assert response.status_code == 400


def test_end_time_equal_to_start_time_is_rejected(client, platform_admin):
    """Zero-duration labor is a mistake, not a valid entry."""
    token = _owner_token(client, platform_admin, email="owner-labor2-equal@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-labor2-equal@example.com")
    job_id = _job(client, token)
    entry_id = _open_entry(client, token, job_id, tech_id).json()["id"]

    response = client.patch(
        f"/api/v1/jobs/{job_id}/labor-entries/{entry_id}",
        json={"end_time": START.isoformat()},
        headers=h,
    )

    assert response.status_code == 400


def test_entry_on_an_invoiced_job_cannot_be_changed(client, db_session, platform_admin):
    """Labor is billed at invoice time; changing it afterwards would make an
    already-issued invoice disagree with the job.

    The invoicing endpoints aren't on this branch yet, and the job status
    machine deliberately blocks reaching `invoiced` manually, so the status is
    set directly here. The guard has to exist before invoicing ships, not after.
    """
    from app.models.job import Job, JobStatus

    token = _owner_token(client, platform_admin, email="owner-labor2-invoiced@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-labor2-invoiced@example.com")
    job_id = _job(client, token)
    entry_id = _open_entry(client, token, job_id, tech_id).json()["id"]

    db_session.query(Job).filter(Job.id == job_id).one().status = JobStatus.invoiced
    db_session.commit()

    response = client.patch(
        f"/api/v1/jobs/{job_id}/labor-entries/{entry_id}",
        json={"end_time": (START + timedelta(hours=9)).isoformat()},
        headers=h,
    )

    assert response.status_code == 400


def test_unknown_entry_returns_404(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor2-missing@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)

    response = client.patch(
        f"/api/v1/jobs/{job_id}/labor-entries/does-not-exist",
        json={"end_time": START.isoformat()},
        headers=h,
    )

    assert response.status_code == 404


def test_entry_belonging_to_a_different_job_returns_404(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor2-xjob@example.com")
    h = {"Authorization": f"Bearer {token}"}
    tech_id = _technician_id(client, token, email="tech-labor2-xjob@example.com")
    job_a = _job(client, token)
    job_b = _job(client, token)
    entry_id = _open_entry(client, token, job_a, tech_id).json()["id"]

    response = client.patch(
        f"/api/v1/jobs/{job_b}/labor-entries/{entry_id}",
        json={"end_time": (START + timedelta(hours=1)).isoformat()},
        headers=h,
    )

    assert response.status_code == 404


def test_technician_cannot_close_a_labor_entry(client, platform_admin):
    """Labor is staff-recorded; technicians don't use the app."""
    owner_token = _owner_token(client, platform_admin, email="owner-labor2-role@example.com")
    tech_id = _technician_id(client, owner_token, email="tech-labor2-role@example.com")
    job_id = _job(client, owner_token)
    entry_id = _open_entry(client, owner_token, job_id, tech_id).json()["id"]
    tech_token = client.post(
        "/api/v1/auth/login",
        json={"email": "tech-labor2-role@example.com", "password": "techpass123"},
    ).json()["access_token"]

    response = client.patch(
        f"/api/v1/jobs/{job_id}/labor-entries/{entry_id}",
        json={"end_time": (START + timedelta(hours=1)).isoformat()},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403
