"""GET /technicians — lets staff (not just owner/manager) pick a technician
for job assignment and the labour timer, without exposing GET /users (which
carries email/role for every user and is owner+manager only).
"""


def _owner_token(client, platform_admin, email="owner-tech@example.com", password="ownerpass123"):
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _make_user(client, token, role, email):
    return client.post(
        "/api/v1/users",
        json={"name": role.title(), "email": email, "password": "userpass123", "role": role},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def test_frontdesk_can_list_technicians(client, platform_admin):
    """The gap this closes: frontdesk can assign jobs and start timers, but
    GET /users (owner+manager only) never let them see who to pick."""
    owner_token = _owner_token(client, platform_admin)
    tech_id = _make_user(client, owner_token, "technician", "tech-list@example.com")
    _make_user(client, owner_token, "frontdesk", "fd-list@example.com")
    fd_token = client.post(
        "/api/v1/auth/login", json={"email": "fd-list@example.com", "password": "userpass123"}
    ).json()["access_token"]

    response = client.get(
        "/api/v1/technicians", headers={"Authorization": f"Bearer {fd_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == tech_id
    assert body["items"][0]["name"] == "Technician"


def test_response_excludes_email_and_role(client, platform_admin):
    """Only id and name — this is a picker, not a staff directory."""
    owner_token = _owner_token(client, platform_admin, email="owner-tech-shape@example.com")
    _make_user(client, owner_token, "technician", "tech-shape@example.com")

    body = client.get(
        "/api/v1/technicians", headers={"Authorization": f"Bearer {owner_token}"}
    ).json()

    assert set(body["items"][0].keys()) == {"id", "name"}


def test_non_technician_staff_are_excluded(client, platform_admin):
    owner_token = _owner_token(client, platform_admin, email="owner-tech-filter@example.com")
    _make_user(client, owner_token, "manager", "mgr-filter@example.com")
    _make_user(client, owner_token, "frontdesk", "fd-filter@example.com")

    body = client.get(
        "/api/v1/technicians", headers={"Authorization": f"Bearer {owner_token}"}
    ).json()

    assert body["total"] == 0


def test_technician_cannot_call_the_endpoint(client, platform_admin):
    """This is a picker for staff who assign work, not for technicians
    themselves — matches GET /jobs restricting technicians to their own jobs."""
    owner_token = _owner_token(client, platform_admin, email="owner-tech-role@example.com")
    _make_user(client, owner_token, "technician", "tech-role@example.com")
    tech_token = client.post(
        "/api/v1/auth/login", json={"email": "tech-role@example.com", "password": "userpass123"}
    ).json()["access_token"]

    response = client.get(
        "/api/v1/technicians", headers={"Authorization": f"Bearer {tech_token}"}
    )

    assert response.status_code == 403


def test_list_is_scoped_to_the_tenant(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-tech-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-tech-b@example.com")
    _make_user(client, token_a, "technician", "tech-a@example.com")
    _make_user(client, token_b, "technician", "tech-b@example.com")

    body = client.get(
        "/api/v1/technicians", headers={"Authorization": f"Bearer {token_a}"}
    ).json()

    assert body["total"] == 1
