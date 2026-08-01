import importlib


def test_settings_have_sane_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from app.core import config
    importlib.reload(config)

    assert config.settings.database_url.startswith("sqlite") or config.settings.database_url.startswith("mysql")
    assert config.settings.jwt_secret == "test-secret"
    assert config.settings.jwt_access_expire_minutes > 0
    assert config.settings.jwt_refresh_expire_days > 0


def test_settings_read_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from app.core import config
    importlib.reload(config)

    assert config.settings.database_url == "mysql+pymysql://u:p@localhost/db"
