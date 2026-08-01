def _login(client, platform_admin, email="nimal@colomboauto.lk", password="ownerpass123"):
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
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def test_users_me_requires_auth(client):
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_users_me_returns_current_user(client, platform_admin):
    token = _login(client, platform_admin)

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "nimal@colomboauto.lk"
    assert body["role"] == "owner"
