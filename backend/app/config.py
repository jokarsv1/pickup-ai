"""Runtime configuration. Every value comes from the environment (see .env.example).

Nothing here has a secret default: features whose keys are missing switch themselves
off and the API reports them as unavailable instead of failing at startup.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core -----------------------------------------------------------------
    env: Literal["dev", "test", "prod"] = "dev"
    public_base_url: str = "http://localhost:8000"  # https URL the phone network can reach
    database_url: str = "sqlite+aiosqlite:///./pickup.db"
    redis_url: str | None = None  # enables multi-instance event fan-out
    jwt_secret: str = Field(default="dev-only-secret-change-me-in-production-0000", min_length=32)
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 60
    admin_token: str | None = None  # protects /admin endpoints
    default_country: str = "IN"  # used to parse local phone numbers
    outbound_countries: list[str] = ["IN"]  # the assistant only calls numbers in these countries
    outbound_daily_limit: int = 10  # calls the assistant may place for one user per 24 hours
    outbound_pending_limit: int = 5  # calls waiting to be placed at once
    cors_origins: list[str] = []

    # --- Auth -----------------------------------------------------------------
    firebase_project_id: str | None = None  # verifies Firebase phone-auth ID tokens
    dev_auth_enabled: bool = True  # fixed OTP login for local development only
    dev_auth_code: str = "123456"
    # Closed beta without Firebase SMS costs: these numbers may sign in with BETA_LOGIN_CODE,
    # also in production. Comma-separated, e.g. "+919876543210,+919812345678".
    beta_login_numbers: str = ""
    beta_login_code: str | None = None

    # --- Push (Firebase Cloud Messaging HTTP v1) ---------------------------------
    fcm_service_account_file: str | None = None
    fcm_service_account_json: str | None = None
    # iPhone push (Apple Push Notification service): the .p8 key's contents, its key ID and team ID.
    apns_key_p8: str | None = None
    apns_key_id: str | None = None
    apple_team_id: str | None = None
    ios_bundle_id: str = "ai.pickup.app"
    apns_sandbox: bool = False  # True only for builds run from Xcode; TestFlight uses production

    # --- AI -------------------------------------------------------------------
    anthropic_api_key: str | None = None
    claude_model: str = "claude-haiku-5-5"  # live calls, summaries and the assistant chat (CLAUDE_MODEL overrides)
    claude_live_effort: Literal["low", "medium", "high"] = "low"
    stt_provider: Literal["sarvam", "deepgram"] = "sarvam"
    tts_provider: Literal["sarvam", "elevenlabs", "cartesia"] = "sarvam"
    sarvam_api_key: str | None = None
    sarvam_stt_model: str = "saaras:v3-realtime"
    sarvam_tts_model: str = "bulbul:v3"
    deepgram_api_key: str | None = None
    deepgram_model: str = "nova-3"
    elevenlabs_api_key: str | None = None
    elevenlabs_model: str = "eleven_flash_v2_5"
    cartesia_api_key: str | None = None
    cartesia_model: str = "sonic-3"

    # --- Telephony ------------------------------------------------------------
    telephony_provider: Literal["exotel", "plivo", "twilio"] = "exotel"
    telephony_webhook_secret: str = Field(default="dev-webhook-secret", min_length=8)
    exotel_account_sid: str | None = None
    exotel_api_key: str | None = None
    exotel_api_token: str | None = None
    exotel_subdomain: str = "api.exotel.com"  # api.in.exotel.com for the Mumbai cluster
    exotel_outbound_flow_id: str | None = None  # flow with the Voicebot applet, for outbound calls
    plivo_auth_id: str | None = None
    plivo_auth_token: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    max_call_seconds: int = 300

    # --- Storage --------------------------------------------------------------
    recordings_dir: str = "./recordings"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None

    # --- Legal pages (/legal/privacy, /legal/terms) ---------------------------------
    legal_entity_name: str = "Pickup"
    legal_address: str = "India"
    legal_jurisdiction_city: str = "Bengaluru"
    support_email: str = "support@example.com"
    grievance_officer: str = "The Pickup team"

    # --- Product --------------------------------------------------------------
    trial_days: int = 7
    free_calls_per_month: int = 15
    google_play_package_name: str = "ai.pickup.app"
    google_play_service_account_file: str | None = None
    google_play_service_account_json: str | None = None  # the file's contents (for hosts without files)
    play_pro_product_ids: list[str] = ["pickup_pro_monthly", "pickup_pro_yearly"]

    @property
    def is_dev(self) -> bool:
        return self.env in ("dev", "test")

    @property
    def beta_numbers(self) -> set[str]:
        from app.phone import normalize

        return {n for n in (normalize(x.strip()) for x in self.beta_login_numbers.split(",") if x.strip()) if n}

    @property
    def beta_login_enabled(self) -> bool:
        return bool(self.beta_numbers and self.beta_login_code and len(self.beta_login_code) >= 6)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def public_ws_base_url(self) -> str:
        if self.public_base_url.startswith("https://"):
            return "wss://" + self.public_base_url[len("https://") :]
        if self.public_base_url.startswith("http://"):
            return "ws://" + self.public_base_url[len("http://") :]
        return self.public_base_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
