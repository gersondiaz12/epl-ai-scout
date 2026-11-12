"""API tests run against the epl_scout_test database (created by
docker/initdb). The schema is built with the real Alembic migration, so the
tests also prove the migration matches the models.
"""

import argparse
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db import get_session
from app.main import app

API_ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "player_season_stats, player_source_ids, club_source_ids, club_seasons, players, clubs, seasons"
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = settings.test_database_url
    config = Config(str(API_ROOT / "alembic.ini"))
    config.cmd_opts = argparse.Namespace(x=[f"db_url={url}"])
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    yield sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
