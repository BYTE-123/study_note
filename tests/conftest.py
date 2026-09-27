import pytest

from app import create_app
from config import TestingConfig


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(TestingConfig, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(TestingConfig, "UPLOAD_DIR", str(tmp_path / "uploads"))
    return create_app(TestingConfig)


@pytest.fixture
def client(app):
    return app.test_client()
