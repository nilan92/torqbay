def _owner_token(client, platform_admin, email="owner-jobdu@example.com", password="ownerpass123"):
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


def _create_job(client, token, title="Brake pad replacement", assigned_technician_id=None):
    customer_id = client.post(
        "/api/v1/customers", json={"name": "Nimal Perera"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    payload = {"customer_id": customer_id, "asset_id": asset_id, "title": title}
    if assigned_technician_id:
        payload["assigned_technician_id"] = assigned_technician_id
    return client.post("/api/v1/jobs", json=payload, headers={"Authorization": f"Bearer {token}"}).json()


def _create_technician(client, owner_token, email="tech-jobdu@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    token = login.json()["access_token"]
    tech_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    return token, tech_id


def test_owner_can_get_and_update_a_job(client, platform_admin):
    token = _owner_token(client, platform_admin)
    job = _create_job(client, token)

    get_response = client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Brake pad replacement"

    update_response = client.patch(
        f"/api/v1/jobs/{job['id']}",
        json={"description": "Front and rear pads"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Front and rear pads"
    assert update_response.json()["title"] == "Brake pad replacement"


def test_technician_can_view_only_their_own_assigned_job(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobdu2@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-jobdu2@example.com")
    assigned_job = _create_job(client, token, title="Assigned job", assigned_technician_id=tech_id)
    other_job = _create_job(client, token, title="Someone else's job")

    assigned_response = client.get(
        f"/api/v1/jobs/{assigned_job['id']}", headers={"Authorization": f"Bearer {tech_token}"}
    )
    other_response = client.get(
        f"/api/v1/jobs/{other_job['id']}", headers={"Authorization": f"Bearer {tech_token}"}
    )

    assert assigned_response.status_code == 200
    assert other_response.status_code == 404


def test_technician_cannot_patch_job_fields(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobdu3@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-jobdu3@example.com")
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}",
        json={"title": "Technician trying to rename"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403
