from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DevAtlas API"
    database_url: str = "postgresql+asyncpg://devatlas:devatlas@localhost:5432/devatlas"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]
    openai_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    answer_model: str = "gpt-4.1-mini"
    auth_jwt_secret: SecretStr | None = None
    auth_jwks_url: str | None = None
    auth_jwt_issuer: str = "devatlas-local"
    auth_jwt_audience: str = "devatlas-api"
    auth_cognito_client_id: str | None = None
    auth_development_mode: bool = False
    observability_metrics_token: SecretStr | None = None

    @field_validator(
        "openai_api_key",
        "auth_jwt_secret",
        "observability_metrics_token",
        mode="before",
    )
    @classmethod
    def empty_secret_is_unconfigured(cls, value: object) -> object:
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

    @model_validator(mode="after")
    def development_auth_requires_signing_secret(self) -> "Settings":
        if self.auth_development_mode and self.auth_jwt_secret is None:
            raise ValueError("auth_jwt_secret is required in development auth mode")
        if self.auth_jwt_secret is not None and self.auth_jwks_url is not None:
            raise ValueError(
                "configure either auth_jwt_secret or auth_jwks_url, not both"
            )
        if self.auth_jwks_url is not None and not self.auth_jwks_url.startswith(
            "https://"
        ):
            raise ValueError("auth_jwks_url must use HTTPS")
        if self.auth_cognito_client_id is not None and self.auth_jwks_url is None:
            raise ValueError("auth_cognito_client_id requires auth_jwks_url")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
