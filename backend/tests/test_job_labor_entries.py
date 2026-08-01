def _owner_token(client, platform_admin, email="owner-labor@example.com", password="ownerpass123"):
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


def _create_technician(client, owner_token, email="tech-labor@example.com"):
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


def test_owner_can_log_time_for_a_technician(client, platform_admin):
    token = _owner_token(client, platform_admin)
    _tech_token, tech_id = _create_technician(client, token)
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/labor-entries",
        json={
            "start_time": "2026-08-01T09:00:00Z",
            "end_time": "2026-08-01T10:30:00Z",
            "hourly_rate": 1500.0,
            "technician_id": tech_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["job_id"] == job["id"]
    assert body["technician_id"] == tech_id
    assert body["hourly_rate"] == 1500.0


def test_technician_role_cannot_log_time(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor2@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-labor2@example.com")
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/labor-entries",
        json={"start_time": "2026-08-01T09:00:00Z", "hourly_rate": 1500.0, "technician_id": tech_id},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403


def test_labor_entry_rejects_unknown_technician(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor3@example.com")
    job = _create_job(client, token)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/labor-entries",
        json={"start_time": "2026-08-01T09:00:00Z", "hourly_rate": 1500.0, "technician_id": "does-not-exist"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_labor_entry_for_job_in_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-labor-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-labor-b@example.com")
    _tech_token, tech_id_b = _create_technician(client, token_b, email="tech-labor-b@example.com")
    job_a = _create_job(client, token_a)

    response = client.post(
        f"/api/v1/jobs/{job_a['id']}/labor-entries",
        json={"start_time": "2026-08-01T09:00:00Z", "hourly_rate": 1500.0, "technician_id": tech_id_b},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404
