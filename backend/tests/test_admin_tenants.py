def test_create_tenant_requires_admin_auth(client):
    response = client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Nimal Perera",
            "owner_email": "nimal@colomboauto.lk",
            "owner_password": "ownerpass123",
        },
    )

    assert response.status_code == 401


def test_admin_can_create_tenant_with_owner(client, platform_admin):
    login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    token = login.json()["access_token"]

    response = client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Nimal Perera",
            "owner_email": "nimal@colomboauto.lk",
            "owner_password": "ownerpass123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Colombo Auto Repair"
    assert body["is_active"] is True
    assert body["currency"] == "LKR"
