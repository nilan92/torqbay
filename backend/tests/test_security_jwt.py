import pytest
from fastapi import HTTPException

from app.core.security import create_access_token, create_refresh_token, decode_token


def test_access_token_roundtrip():
    token = create_access_token("user-123", "tenant_user")

    payload = decode_token(token, audience="tenant_user", token_type="access")

    assert payload["sub"] == "user-123"
    assert payload["aud"] == "tenant_user"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token("user-123", "tenant_user")

    payload = decode_token(token, audience="tenant_user", token_type="refresh")

    assert payload["type"] == "refresh"


def test_decode_token_rejects_garbage():
    with pytest.raises(HTTPException) as exc_info:
        decode_token("not-a-real-token", audience="tenant_user", token_type="access")

    assert exc_info.value.status_code == 401
