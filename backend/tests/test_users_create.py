def _owner_token(client, platform_admin, email="ownerd@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Tenant D Workshop",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def test_owner_can_create_staff_user(client, platform_admin):
    token = _owner_token(client, platform_admin)

    response = client.post(
        "/api/v1/users",
        json={
            "name": "Front Desk",
            "email": "frontdesk@example.com",
            "password": "frontpass123",
            "role": "frontdesk",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "frontdesk"
    assert body["email"] == "frontdesk@example.com"


def test_create_user_rejects_duplicate_email(client, platform_admin):
    token = _owner_token(client, platform_admin, email="ownere@example.com")

    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": "duplicate@example.com", "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = client.post(
        "/api/v1/users",
        json={
            "name": "Tech Two",
            "email": "duplicate@example.com",
            "password": "techpass123",
            "role": "technician",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
