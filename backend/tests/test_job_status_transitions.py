def _owner_token(client, platform_admin, email="owner-status@example.com", password="ownerpass123"):
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
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _create_technician(client, owner_token, email="tech-status@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    token = login.json()["access_token"]
    tech_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    return token, tech_id


def _create_job(client, token, assigned_technician_id=None):
    customer_id = client.post(
        "/api/v1/customers", json={"name": "Nimal Perera"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    payload = {"customer_id": customer_id, "asset_id": asset_id, "title": "Brake pad replacement"}
    if assigned_technician_id:
        payload["assigned_technician_id"] = assigned_technician_id
    return client.post("/api/v1/jobs", json=payload, headers={"Authorization": f"Bearer {token}"}).json()


def test_owner_can_walk_a_job_through_the_happy_path(client, platform_admin):
    token = _owner_token(client, platform_admin)
    job = _create_job(client, token)

    to_in_progress = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert to_in_progress.status_code == 200
    assert to_in_progress.json()["status"] == "in_progress"
    assert to_in_progress.json()["started_at"] is not None

    to_done = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert to_done.status_code == 200
    assert to_done.json()["status"] == "done"
    assert to_done.json()["completed_at"] is not None


def test_cannot_skip_from_open_directly_to_done(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status2@example.com")
    job = _create_job(client, token)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_cannot_manually_set_invoiced_status(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status3@example.com")
    job = _create_job(client, token)
    client.patch(
        f"/api/v1/jobs/{job['id']}/status", json={"status": "in_progress"}, headers={"Authorization": f"Bearer {token}"}
    )
    client.patch(
        f"/api/v1/jobs/{job['id']}/status", json={"status": "done"}, headers={"Authorization": f"Bearer {token}"}
    )

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "invoiced"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_assigned_technician_can_transition_their_own_job(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status4@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-status4@example.com")
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_technician_cannot_transition_an_unassigned_job(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status5@example.com")
    tech_token, _tech_id = _create_technician(client, token, email="tech-status5@example.com")
    job = _create_job(client, token)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 404
