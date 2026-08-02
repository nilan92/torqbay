def _owner_token(client, platform_admin, email="owner-lowstock@example.com", password="ownerpass123"):
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


def _create_item(client, token, sku, quantity_on_hand, reorder_threshold):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": f"Item {sku}",
            "unit_cost": 100.0,
            "unit_price": 200.0,
            "quantity_on_hand": quantity_on_hand,
            "reorder_threshold": reorder_threshold,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_low_stock_filter_returns_only_items_at_or_below_threshold(client, platform_admin):
    token = _owner_token(client, platform_admin)
    _create_item(client, token, "PLENTY", quantity_on_hand=20.0, reorder_threshold=5.0)
    _create_item(client, token, "AT-THRESHOLD", quantity_on_hand=5.0, reorder_threshold=5.0)
    _create_item(client, token, "BELOW", quantity_on_hand=1.0, reorder_threshold=5.0)

    response = client.get(
        "/api/v1/inventory-items?low_stock=true", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["sku"] for item in body["items"]} == {"AT-THRESHOLD", "BELOW"}


def test_without_the_filter_all_items_are_returned(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-lowstock-all@example.com")
    _create_item(client, token, "PLENTY", quantity_on_hand=20.0, reorder_threshold=5.0)
    _create_item(client, token, "BELOW", quantity_on_hand=1.0, reorder_threshold=5.0)

    response = client.get("/api/v1/inventory-items", headers={"Authorization": f"Bearer {token}"})

    assert response.json()["total"] == 2


def test_low_stock_false_returns_all_items(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-lowstock-false@example.com")
    _create_item(client, token, "PLENTY", quantity_on_hand=20.0, reorder_threshold=5.0)
    _create_item(client, token, "BELOW", quantity_on_hand=1.0, reorder_threshold=5.0)

    response = client.get(
        "/api/v1/inventory-items?low_stock=false", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["total"] == 2
