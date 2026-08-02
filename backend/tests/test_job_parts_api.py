def _owner_token(client, platform_admin, email="owner-jobpart@example.com", password="ownerpass123"):
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


def _item(client, token, sku="BP-001", quantity_on_hand=10.0):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": "Brake pad set",
            "unit_cost": 2500.0,
            "unit_price": 4000.0,
            "quantity_on_hand": quantity_on_hand,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _on_hand(client, token, item_id):
    return client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["quantity_on_hand"]


def test_recording_a_part_decrements_stock_and_snapshots_prices(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token, quantity_on_hand=10.0)

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 3.0},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 3.0
    assert body["unit_cost_at_time"] == 2500.0
    assert body["unit_price_at_time"] == 4000.0
    assert body["overdrawn"] is False
    assert body["shortfall"] == 0.0
    assert _on_hand(client, token, item_id) == 7.0


def test_later_price_change_does_not_alter_recorded_snapshot(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobpart-snap@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token)

    part = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 1.0},
        headers=headers,
    ).json()

    client.patch(
        f"/api/v1/inventory-items/{item_id}", json={"unit_price": 9999.0}, headers=headers
    )

    assert part["unit_price_at_time"] == 4000.0


def test_using_more_than_on_hand_clamps_at_zero_and_flags_overdrawn(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobpart-over@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token, quantity_on_hand=2.0)

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 5.0},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 5.0
    assert body["overdrawn"] is True
    assert body["shortfall"] == 3.0
    assert _on_hand(client, token, item_id) == 0.0


def test_quantity_must_be_positive(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobpart-zero@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token)

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 0},
        headers=headers,
    )

    assert response.status_code == 422


def test_item_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-jobpart-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-jobpart-b@example.com")
    job_id = _job(client, token_a)
    foreign_item_id = _item(client, token_b, sku="B-1")

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": foreign_item_id, "quantity": 1.0},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 404


def test_job_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-jobpart-j-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-jobpart-j-b@example.com")
    job_id = _job(client, token_a)
    item_id = _item(client, token_b, sku="B-2")

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 1.0},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404
