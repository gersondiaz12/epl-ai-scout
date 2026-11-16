import pytest
from pydantic import ValidationError

from app.config import ENV_FILE, Settings

URL = "postgresql+psycopg://user:secret@db.example:5432/scout"


def test_env_file_is_found_from_the_module_not_the_working_directory():
    assert ENV_FILE.name == ".env"
    assert ENV_FILE.parent.name == "api"


def test_test_database_defaults_to_same_server_with_suffix(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    settings = Settings(_env_file=None, database_url=URL)
    assert settings.test_database_url == URL + "_test"


def test_explicit_test_database_wins():
    other = "postgresql+psycopg://user:secret@other:5432/elsewhere"
    settings = Settings(_env_file=None, database_url=URL, test_database_url=other)
    assert settings.test_database_url == other


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
