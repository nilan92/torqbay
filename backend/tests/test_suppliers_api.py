def _owner_token(client, platform_admin, email="owner-supplier@example.com", password="ownerpass123"):
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


def test_owner_can_create_and_list_suppliers(client, platform_admin):
    token = _owner_token(client, platform_admin)

    create_response = client.post(
        "/api/v1/suppliers",
        json={"name": "Lanka Parts Ltd", "contact_info": "011-2345678"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    assert create_response.json()["name"] == "Lanka Parts Ltd"

    list_response = client.get("/api/v1/suppliers", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["items"][0]["contact_info"] == "011-2345678"


def test_supplier_can_be_fetched_and_updated(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-supplier-2@example.com")
    supplier_id = client.post(
        "/api/v1/suppliers",
        json={"name": "Old Name"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]

    get_response = client.get(
        f"/api/v1/suppliers/{supplier_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 200

    patch_response = client.patch(
        f"/api/v1/suppliers/{supplier_id}",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "New Name"


def test_supplier_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-supplier-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-supplier-b@example.com")
    supplier_id = client.post(
        "/api/v1/suppliers",
        json={"name": "Tenant A Supplier"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()["id"]

    response = client.get(
        f"/api/v1/suppliers/{supplier_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404


def test_creating_a_supplier_requires_authentication(client):
    response = client.post("/api/v1/suppliers", json={"name": "No Auth"})
    assert response.status_code == 401
