def _owner_token(client, platform_admin, email="owner-partlist@example.com", password="ownerpass123"):
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


def _item(client, token, sku):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": f"Item {sku}",
            "unit_cost": 100.0,
            "unit_price": 200.0,
            "quantity_on_hand": 50.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def test_listing_parts_returns_only_that_jobs_parts(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    job_a = _job(client, token)
    job_b = _job(client, token)
    item_id = _item(client, token, "SHARED")

    client.post(
        f"/api/v1/jobs/{job_a}/parts",
        json={"inventory_item_id": item_id, "quantity": 2.0},
        headers=headers,
    )
    client.post(
        f"/api/v1/jobs/{job_b}/parts",
        json={"inventory_item_id": item_id, "quantity": 5.0},
        headers=headers,
    )

    response = client.get(f"/api/v1/jobs/{job_a}/parts", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["quantity"] == 2.0


def test_listing_parts_for_another_tenants_job_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-partlist-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-partlist-b@example.com")
    job_id = _job(client, token_a)

    response = client.get(
        f"/api/v1/jobs/{job_id}/parts", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response.status_code == 404
