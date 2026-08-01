def _owner_token(client, platform_admin, email="owner-asset@example.com", password="ownerpass123"):
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


def _create_customer(client, token, name="Nimal Perera"):
    response = client.post(
        "/api/v1/customers",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


def test_owner_can_create_and_list_assets_for_a_customer(client, platform_admin):
    token = _owner_token(client, platform_admin)
    customer_id = _create_customer(client, token)

    create_response = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla 2018", "identifier": "ABC-1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["customer_id"] == customer_id
    assert body["label"] == "Toyota Corolla 2018"

    list_response = client.get(
        f"/api/v1/customers/{customer_id}/assets", headers={"Authorization": f"Bearer {token}"}
    )
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["identifier"] == "ABC-1234"


def test_assets_for_customer_in_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-asset-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-asset-b@example.com")
    customer_id = _create_customer(client, token_a)

    response = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Should not work"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404


def test_asset_creation_requires_staff_role(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-asset-c@example.com")
    customer_id = _create_customer(client, token)

    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": "tech-asset@example.com", "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {token}"},
    )
    tech_login = client.post(
        "/api/v1/auth/login", json={"email": "tech-asset@example.com", "password": "techpass123"}
    )
    tech_token = tech_login.json()["access_token"]

    response = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Should not work"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403
