def _owner_token(client, platform_admin, email="owner-postatus@example.com", password="ownerpass123"):
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


def _draft_po(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = client.post("/api/v1/suppliers", json={"name": "S"}, headers=headers).json()["id"]
    item_id = client.post(
        "/api/v1/inventory-items",
        json={"sku": "S-1", "name": "Item", "unit_cost": 1.0, "unit_price": 2.0},
        headers=headers,
    ).json()["id"]
    return client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 1.0, "unit_cost": 1.0}],
        },
        headers=headers,
    ).json()["id"]


def test_draft_can_move_to_ordered(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    po_id = _draft_po(client, token)

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/status", json={"status": "ordered"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ordered"


def test_status_endpoint_cannot_set_received(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-postatus-recv@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    po_id = _draft_po(client, token)

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/status", json={"status": "received"}, headers=headers
    )

    assert response.status_code == 400


def test_received_order_cannot_change_status(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-postatus-after@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    po_id = _draft_po(client, token)
    client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/status", json={"status": "ordered"}, headers=headers
    )

    assert response.status_code == 400
