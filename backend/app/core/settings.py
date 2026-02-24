from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "kidneystone-ai"
    api_prefix: str = "/api"
    env: str = "dev"
    allow_origins: str = "http://localhost:3000"
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
    disable_scheduled_sms: bool = False

    # Telnyx (SMS + SIP)
    telnyx_api_key: str | None = None
    telnyx_messaging_profile_id: str | None = None
    telnyx_sip_connection_id: str | None = None
    telnyx_phone_number: str | None = None
    telnyx_base_url: str = "https://api.telnyx.com/v2"

    # Vapi
    vapi_api_key: str | None = None
    vapi_assistant_id: str | None = None
    vapi_phone_number_id: str | None = None
    vapi_webhook_secret: str | None = None
    vapi_base_url: str = "https://api.vapi.ai"
    vapi_call_path: str = "/call"
    vapi_model: str = "gpt-5.2-chat-latest"

    redis_url: str = "redis://localhost:6379/0"

    context_rebuild_mode: str = "async"

    otp_ttl_seconds: int = 300
    otp_rate_limit: int = 3
    otp_rate_window_seconds: int = 600
    otp_max_attempts: int = 5
    otp_length: int = 6

    jwt_secret: str = "dev-secret"
    jwt_expiry_days: int = 30
    jwt_cookie_name: str = "ks_session"
    jwt_cookie_secure: bool = False
    jwt_algorithm: str = "HS256"

    frontend_base_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
