from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_DB = "postgresql+psycopg://scout:scout@localhost:5433/epl_scout"


class Settings(BaseSettings):
    """Read from environment variables, then apps/api/.env if present."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = _LOCAL_DB
    test_database_url: str = _LOCAL_DB + "_test"


settings = Settings()
