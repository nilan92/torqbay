from app.core.security import hash_password, verify_password


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery-staple")

    assert not verify_password("wrong-password", hashed)
