from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DevAtlas API"
    database_url: str = "postgresql+asyncpg://devatlas:devatlas@localhost:5432/devatlas"
    cors_origins: list[str] = ["http://localhost:5173"]
    openai_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def empty_openai_key_is_unconfigured(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("embedding_dimension")
    @classmethod
    def dimension_matches_schema(cls, value: int) -> int:
        if value != 1536:
            raise ValueError("embedding_dimension must be 1536 for the current schema")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
