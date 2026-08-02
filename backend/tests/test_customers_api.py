def _owner_token(client, platform_admin, email="owner-cust@example.com", password="ownerpass123"):
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


def _technician_token(client, platform_admin, owner_token, email="tech-cust@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    return login.json()["access_token"]


def test_owner_can_create_and_list_customers(client, platform_admin):
    token = _owner_token(client, platform_admin)

    create_response = client.post(
        "/api/v1/customers",
        json={"name": "Nimal Perera", "phone": "+94771234567"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "Nimal Perera"
    assert body["phone"] == "+94771234567"

    list_response = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["name"] == "Nimal Perera"


def test_technician_cannot_create_customer(client, platform_admin):
    owner_token = _owner_token(client, platform_admin, email="owner-cust2@example.com")
    tech_token = _technician_token(client, platform_admin, owner_token, email="tech-cust2@example.com")

    response = client.post(
        "/api/v1/customers",
        json={"name": "Nimal Perera"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403


def test_get_and_update_customer(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-cust3@example.com")
    create_response = client.post(
        "/api/v1/customers",
        json={"name": "Nimal Perera"},
        headers={"Authorization": f"Bearer {token}"},
    )
    customer_id = create_response.json()["id"]

    get_response = client.get(f"/api/v1/customers/{customer_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Nimal Perera"

    update_response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"phone": "+94770000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["phone"] == "+94770000000"
    assert update_response.json()["name"] == "Nimal Perera"


def test_customer_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-cust-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-cust-b@example.com")

    create_response = client.post(
        "/api/v1/customers",
        json={"name": "Tenant A's Customer"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    customer_id = create_response.json()["id"]

    response = client.get(f"/api/v1/customers/{customer_id}", headers={"Authorization": f"Bearer {token_b}"})

    assert response.status_code == 404
