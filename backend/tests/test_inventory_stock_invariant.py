def _admin_token(client, platform_admin):
    return client.post("/api/v1/admin/auth/login", json=platform_admin).json()["access_token"]


def _tenant_owner(client, platform_admin, email, password="ownerpass123"):
    admin_token = _admin_token(client, platform_admin)
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _technician_token(client, owner_token, email="tech-inv@example.com", password="techpass123"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": password, "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _item(client, token, sku="INV-1", quantity_on_hand=0.0):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": "Brake pad set",
            "unit_cost": 2500.0,
            "unit_price": 4000.0,
            "quantity_on_hand": quantity_on_hand,
            "reorder_threshold": 4.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _on_hand(client, token, item_id):
    return client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["quantity_on_hand"]


def _job(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=headers).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=headers,
    ).json()["id"]
    return client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake service"},
        headers=headers,
    ).json()["id"]


def test_receive_then_consume_leaves_correct_stock(client, platform_admin):
    token = _tenant_owner(client, platform_admin, "owner-invariant@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    item_id = _item(client, token, quantity_on_hand=0.0)
    supplier_id = client.post("/api/v1/suppliers", json={"name": "S"}, headers=headers).json()["id"]
    job_id = _job(client, token)

    po_id = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 20.0, "unit_cost": 2400.0}],
        },
        headers=headers,
    ).json()["id"]
    client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)
    assert _on_hand(client, token, item_id) == 20.0

    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 3.0},
        headers=headers,
    )
    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 2.5},
        headers=headers,
    )

    assert _on_hand(client, token, item_id) == 14.5


def test_consumption_drives_an_item_into_the_low_stock_list(client, platform_admin):
    token = _tenant_owner(client, platform_admin, "owner-invariant-low@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    item_id = _item(client, token, quantity_on_hand=10.0)
    job_id = _job(client, token)

    assert client.get("/api/v1/inventory-items?low_stock=true", headers=headers).json()["total"] == 0

    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 7.0},
        headers=headers,
    )

    low = client.get("/api/v1/inventory-items?low_stock=true", headers=headers).json()
    assert low["total"] == 1
    assert low["items"][0]["id"] == item_id


def test_using_exactly_the_quantity_on_hand_is_not_overdrawn(client, platform_admin):
    """Boundary case: available == quantity.

    A Task 7 review proved this is uncovered — the mutation
    `overdrawn = item.quantity_on_hand <= 0` passes every other test in the
    suite and is wrong only here, so without this test that regression ships
    silently.
    """
    token = _tenant_owner(client, platform_admin, "owner-invariant-exact@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    item_id = _item(client, token, quantity_on_hand=5.0)
    job_id = _job(client, token)

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 5.0},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["shortfall"] == 0.0
    assert body["overdrawn"] is False
    assert _on_hand(client, token, item_id) == 0.0


def test_technician_can_read_inventory_but_not_write_it(client, platform_admin):
    owner_token = _tenant_owner(client, platform_admin, "owner-invariant-role@example.com")
    tech_token = _technician_token(client, owner_token)
    tech_headers = {"Authorization": f"Bearer {tech_token}"}
    item_id = _item(client, owner_token, quantity_on_hand=5.0)

    assert client.get("/api/v1/inventory-items", headers=tech_headers).status_code == 200
    assert client.get(f"/api/v1/inventory-items/{item_id}", headers=tech_headers).status_code == 200

    create = client.post(
        "/api/v1/inventory-items",
        json={"sku": "TECH-1", "name": "Nope", "unit_cost": 1.0, "unit_price": 2.0},
        headers=tech_headers,
    )
    assert create.status_code == 403

    patch = client.patch(
        f"/api/v1/inventory-items/{item_id}", json={"unit_price": 1.0}, headers=tech_headers
    )
    assert patch.status_code == 403

    assert client.post("/api/v1/suppliers", json={"name": "Nope"}, headers=tech_headers).status_code == 403
