from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "kidneystone-ai"
    api_prefix: str = "/api"
    env: str = "dev"
    allow_origins: str = "*"
    api_token: str | None = None

    database_url: str = "postgresql://app:app@localhost:5432/kidneystone"

    # Default to Vertex in cloud deployments; override to "mock" or "local" for dev/edge.
    medgemma_mode: str = "vertex"
    medgemma_endpoint: str | None = None
    medgemma_http_url: str | None = None
    medgemma_analyze_url: str | None = None
    medgemma_generate_url: str | None = None
    medgemma_model_path: str | None = None
    medgemma_vertex_endpoint: str | None = None
    medgemma_vertex_project: str | None = None
    medgemma_vertex_location: str | None = None

    storage_mode: str = "auto"
    gcs_bucket: str | None = None
    gcs_prefix: str = "ct-uploads"
    gcs_signed_url_ttl_seconds: int = 900
    local_storage_root: str = "data/ct_scans"

    messaging_mode: str = "mock"
    messaging_api_key: str | None = None
    messaging_phone_number: str | None = None
    messaging_profile_id: str | None = None
    messaging_voice_connection_id: str | None = None
    messaging_webhook_base_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
