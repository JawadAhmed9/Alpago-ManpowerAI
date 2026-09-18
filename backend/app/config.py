from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Everything is env-driven; nothing is hardcoded to sample sizes."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Alpago Manpower Allocation & Scheduling"
    environment: str = "development"

    # Data layer
    database_url: str = "postgresql+psycopg2://alpago:alpago@db:5432/alpago"

    # CORS
    cors_origins: str = "*"

    # --- AI layer (deliberately thin, always optional) -----------------
    ai_enabled: bool = True
    ai_provider: str = "groq"
    ai_api_key: str | None = None
    ai_model: str = "qwen/qwen3.8-27b"
    ai_base_url: str = "https://api.groq.com/openai/v1"
    ai_timeout_seconds: float = 20.0
    # Hard ceiling so a runaway allocation run can never burn the free tier.
    ai_max_items_per_run: int = 40

    # --- Allocation scoring weights (tunable without a code change) ----
    skill_weight_senior: float = 3.0
    skill_weight_mid: float = 2.0
    skill_weight_junior: float = 1.0
    # How strongly to prefer the least-loaded employee (points per allocated day).
    workload_penalty_per_day: float = 0.15

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
