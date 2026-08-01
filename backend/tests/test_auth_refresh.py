def _create_tenant_and_login(client, platform_admin, email="refresh-owner@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Refresh Test Workshop",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()


def test_refresh_returns_new_access_token(client, platform_admin):
    tokens = _create_tenant_and_login(client, platform_admin)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_refresh_rejects_an_access_token(client, platform_admin):
    tokens = _create_tenant_and_login(client, platform_admin)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})

    assert response.status_code == 401


def test_refresh_rejects_garbage_token(client):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401
