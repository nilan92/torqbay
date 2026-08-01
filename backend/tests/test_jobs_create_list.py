def _owner_token(client, platform_admin, email="owner-job@example.com", password="ownerpass123"):
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


def _create_customer_and_asset(client, token):
    customer_id = client.post(
        "/api/v1/customers", json={"name": "Nimal Perera"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    return customer_id, asset_id


def _create_technician(client, owner_token, email="tech-job@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    return login.json()["access_token"], login.json()


def test_owner_can_create_a_job(client, platform_admin):
    token = _owner_token(client, platform_admin)
    customer_id, asset_id = _create_customer_and_asset(client, token)

    response = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake pad replacement"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Brake pad replacement"
    assert body["status"] == "open"
    assert body["customer_id"] == customer_id
    assert body["asset_id"] == asset_id


def test_create_job_rejects_unknown_customer(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-job2@example.com")
    _, asset_id = _create_customer_and_asset(client, token)

    response = client.post(
        "/api/v1/jobs",
        json={"customer_id": "does-not-exist", "asset_id": asset_id, "title": "Should fail"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_technician_only_sees_assigned_jobs(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-job3@example.com")
    customer_id, asset_id = _create_customer_and_asset(client, token)
    tech_token, tech_login = _create_technician(client, token, email="tech-job3@example.com")
    tech_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tech_token}"}).json()["id"]

    assigned_job = client.post(
        "/api/v1/jobs",
        json={
            "customer_id": customer_id,
            "asset_id": asset_id,
            "title": "Assigned to technician",
            "assigned_technician_id": tech_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Not assigned to anyone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    owner_list = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"}).json()
    tech_list = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {tech_token}"}).json()

    assert owner_list["total"] == 2
    assert tech_list["total"] == 1
    assert tech_list["items"][0]["id"] == assigned_job["id"]
