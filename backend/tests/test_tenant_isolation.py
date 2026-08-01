def _create_tenant_owner_and_login(client, platform_admin, tenant_name, email, password):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={"name": tenant_name, "owner_name": "Owner", "owner_email": email, "owner_password": password},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def test_tenant_cannot_see_another_tenants_users(client, platform_admin):
    token_a = _create_tenant_owner_and_login(
        client, platform_admin, "Tenant A Workshop", "ownera@example.com", "passwordA123"
    )
    token_b = _create_tenant_owner_and_login(
        client, platform_admin, "Tenant B Workshop", "ownerb@example.com", "passwordB123"
    )

    response_a = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token_a}"})
    response_b = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token_b}"})

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    emails_visible_to_a = {user["email"] for user in response_a.json()}
    emails_visible_to_b = {user["email"] for user in response_b.json()}

    assert emails_visible_to_a == {"ownera@example.com"}
    assert emails_visible_to_b == {"ownerb@example.com"}


def test_technician_cannot_list_users(client, platform_admin):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Tenant C Workshop",
            "owner_name": "Owner",
            "owner_email": "ownerc@example.com",
            "owner_password": "passwordC123",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    owner_login = client.post(
        "/api/v1/auth/login", json={"email": "ownerc@example.com", "password": "passwordC123"}
    )
    owner_token = owner_login.json()["access_token"]

    client.post(
        "/api/v1/users",
        json={"name": "Tech One", "email": "tech1@example.com", "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    tech_login = client.post("/api/v1/auth/login", json={"email": "tech1@example.com", "password": "techpass123"})
    tech_token = tech_login.json()["access_token"]

    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {tech_token}"})

    assert response.status_code == 403
