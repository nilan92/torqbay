def _owner_token(client, platform_admin, email="owner-item@example.com", password="ownerpass123"):
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


def _create_item(client, token, sku="BP-001", **overrides):
    payload = {"sku": sku, "name": "Brake pad set", "unit_cost": 2500.0, "unit_price": 4000.0}
    payload.update(overrides)
    return client.post(
        "/api/v1/inventory-items", json=payload, headers={"Authorization": f"Bearer {token}"}
    )


def test_owner_can_create_and_list_inventory_items(client, platform_admin):
    token = _owner_token(client, platform_admin)

    create_response = _create_item(client, token, quantity_on_hand=10.0, reorder_threshold=3.0)
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["sku"] == "BP-001"
    assert body["quantity_on_hand"] == 10.0

    list_response = client.get("/api/v1/inventory-items", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_quantity_and_threshold_default_to_zero(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-default@example.com")

    body = _create_item(client, token).json()
    assert body["quantity_on_hand"] == 0.0
    assert body["reorder_threshold"] == 0.0


def test_duplicate_sku_in_same_tenant_returns_409(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-dup@example.com")
    assert _create_item(client, token, sku="SAME").status_code == 201

    response = _create_item(client, token, sku="SAME")
    assert response.status_code == 409


def test_item_can_be_updated(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-patch@example.com")
    item_id = _create_item(client, token).json()["id"]

    response = client.patch(
        f"/api/v1/inventory-items/{item_id}",
        json={"unit_price": 4500.0, "reorder_threshold": 5.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["unit_price"] == 4500.0
    assert response.json()["reorder_threshold"] == 5.0


def test_patch_cannot_change_quantity_on_hand(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-qty@example.com")
    item_id = _create_item(client, token, quantity_on_hand=7.0).json()["id"]

    response = client.patch(
        f"/api/v1/inventory-items/{item_id}",
        json={"quantity_on_hand": 999.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["quantity_on_hand"] == 7.0


def test_creating_item_with_supplier_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-item-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-item-b@example.com")
    supplier_id = client.post(
        "/api/v1/suppliers",
        json={"name": "Tenant A Supplier"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()["id"]

    response = _create_item(client, token_b, sku="X-1", supplier_id=supplier_id)
    assert response.status_code == 404


def test_negative_numeric_fields_are_rejected(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-negative@example.com")

    for field in ("unit_cost", "unit_price", "quantity_on_hand", "reorder_threshold"):
        response = _create_item(client, token, sku=f"NEG-{field}", **{field: -1.0})
        assert response.status_code == 422, f"{field} must reject negative values"


def test_patch_rejects_negative_numeric_fields(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-negative-patch@example.com")
    item_id = _create_item(client, token).json()["id"]

    response = client.patch(
        f"/api/v1/inventory-items/{item_id}",
        json={"unit_price": -5.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_item_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-item-iso-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-item-iso-b@example.com")
    item_id = _create_item(client, token_a).json()["id"]

    response = client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404
