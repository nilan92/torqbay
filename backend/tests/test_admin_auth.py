def test_admin_login_with_valid_credentials(client, platform_admin):
    response = client.post("/api/v1/admin/auth/login", json=platform_admin)

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_admin_login_with_wrong_password(client, platform_admin):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": platform_admin["email"], "password": "wrong"},
    )

    assert response.status_code == 401


def test_admin_login_with_unknown_email(client):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "nobody@torqbay.test", "password": "whatever"},
    )

    assert response.status_code == 401
