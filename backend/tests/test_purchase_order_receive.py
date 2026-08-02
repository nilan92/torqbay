def _owner_token(client, platform_admin, email="owner-receive@example.com", password="ownerpass123"):
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


def _supplier(client, token):
    return client.post(
        "/api/v1/suppliers", json={"name": "Lanka Parts Ltd"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]


def _item(client, token, sku="BP-001", quantity_on_hand=0.0):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": f"Item {sku}",
            "unit_cost": 2500.0,
            "unit_price": 4000.0,
            "quantity_on_hand": quantity_on_hand,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _po(client, token, supplier_id, lines):
    return client.post(
        "/api/v1/purchase-orders",
        json={"supplier_id": supplier_id, "items": lines},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _on_hand(client, token, item_id):
    return client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["quantity_on_hand"]


def test_receiving_increments_stock_for_every_line(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_a = _item(client, token, sku="A-1", quantity_on_hand=2.0)
    item_b = _item(client, token, sku="B-1", quantity_on_hand=0.0)
    po_id = _po(
        client,
        token,
        supplier_id,
        [
            {"inventory_item_id": item_a, "quantity": 10.0, "unit_cost": 100.0},
            {"inventory_item_id": item_b, "quantity": 4.0, "unit_cost": 50.0},
        ],
    )

    response = client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"
    assert body["received_at"] is not None
    assert _on_hand(client, token, item_a) == 12.0
    assert _on_hand(client, token, item_b) == 4.0


def test_receiving_twice_returns_409_and_does_not_double_increment(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-receive-twice@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_id = _item(client, token, quantity_on_hand=1.0)
    po_id = _po(client, token, supplier_id, [{"inventory_item_id": item_id, "quantity": 10.0, "unit_cost": 100.0}])

    assert client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers).status_code == 200
    assert _on_hand(client, token, item_id) == 11.0

    second = client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)

    assert second.status_code == 409
    assert _on_hand(client, token, item_id) == 11.0


def test_receiving_another_tenants_purchase_order_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-receive-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-receive-b@example.com")
    supplier_id = _supplier(client, token_a)
    item_id = _item(client, token_a)
    po_id = _po(client, token_a, supplier_id, [{"inventory_item_id": item_id, "quantity": 1.0, "unit_cost": 1.0}])

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/receive", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response.status_code == 404
