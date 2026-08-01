def _create_tenant_and_owner(client, platform_admin, email="nimal@colomboauto.lk", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Nimal Perera",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return email, password


def test_login_with_valid_credentials_returns_tokens(client, platform_admin):
    email, password = _create_tenant_and_owner(client, platform_admin)

    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_login_with_wrong_password_returns_401(client, platform_admin):
    email, _ = _create_tenant_and_owner(client, platform_admin)

    response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})

    assert response.status_code == 401
