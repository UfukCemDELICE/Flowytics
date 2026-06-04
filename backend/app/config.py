from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database (Supabase Postgres direct connection via asyncpg)
    DATABASE_URL: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"      # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT: str = "auto"     # "auto" (TTY=dev, non-TTY=json), "json", "dev"

    # Security
    FERNET_KEY: str = ""         # 32-byte base64-encoded key for Fernet encryption
    FRONTEND_URL: str = "http://localhost:3000"  # For CORS and redirect URLs

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Clerk
    CLERK_SECRET_KEY: str = ""

    # QuickBooks Online
    QB_CLIENT_ID: str = ""
    QB_CLIENT_SECRET: str = ""
    QB_REDIRECT_URI: str = ""
    QB_ENVIRONMENT: str = "sandbox"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Slack
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_APP_TOKEN: str = ""
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
