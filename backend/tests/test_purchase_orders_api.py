def _owner_token(client, platform_admin, email="owner-po@example.com", password="ownerpass123"):
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


def _supplier(client, token, name="Lanka Parts Ltd"):
    return client.post(
        "/api/v1/suppliers", json={"name": name}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]


def _item(client, token, sku="BP-001"):
    return client.post(
        "/api/v1/inventory-items",
        json={"sku": sku, "name": f"Item {sku}", "unit_cost": 2500.0, "unit_price": 4000.0},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def test_owner_can_create_a_purchase_order_with_line_items(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_id = _item(client, token)

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 20.0, "unit_cost": 2400.0}],
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["received_at"] is None
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 20.0


def test_purchase_order_can_be_listed_and_fetched(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-po-list@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_id = _item(client, token)
    po_id = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 5.0, "unit_cost": 100.0}],
        },
        headers=headers,
    ).json()["id"]

    list_response = client.get("/api/v1/purchase-orders", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(f"/api/v1/purchase-orders/{po_id}", headers=headers)
    assert get_response.status_code == 200
    assert len(get_response.json()["items"]) == 1


def test_purchase_order_requires_at_least_one_line_item(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-po-empty@example.com")
    supplier_id = _supplier(client, token)

    response = client.post(
        "/api/v1/purchase-orders",
        json={"supplier_id": supplier_id, "items": []},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_supplier_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-po-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-po-b@example.com")
    foreign_supplier = _supplier(client, token_a)
    item_id = _item(client, token_b, sku="B-1")

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": foreign_supplier,
            "items": [{"inventory_item_id": item_id, "quantity": 1.0, "unit_cost": 1.0}],
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404


def test_line_item_referencing_another_tenants_item_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-po-item-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-po-item-b@example.com")
    supplier_id = _supplier(client, token_b)
    foreign_item = _item(client, token_a, sku="A-1")

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": foreign_item, "quantity": 1.0, "unit_cost": 1.0}],
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404
