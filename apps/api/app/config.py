from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# apps/api/.env, found from this file so it loads whatever the working directory.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Environment variables first, then apps/api/.env (gitignored)."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str
    # Defaults to the same server as DATABASE_URL with "_test" added to the database name.
    test_database_url: str | None = None
    # The self-hosted Transfermarkt API (felipeall/transfermarkt-api). Read only by
    # the scheduled ingest app.ingest.transfermarkt_api, never by a router.
    transfermarkt_api_url: str = "http://127.0.0.1:8100"

    @model_validator(mode="after")
    def _default_test_database(self) -> "Settings":
        if self.test_database_url is None:
            url = make_url(self.database_url)
            self.test_database_url = url.set(database=f"{url.database}_test").render_as_string(
                hide_password=False
            )
        return self


settings = Settings()
