from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database (Supabase Postgres direct connection via asyncpg)
    DATABASE_URL: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Clerk
    CLERK_SECRET_KEY: str = ""

    # Codat
    CODAT_API_KEY: str = ""
    CODAT_BASE_URL: str = "https://api.codat.io"

    # Plaid
    PLAID_CLIENT_ID: str = ""
    PLAID_SECRET: str = ""
    PLAID_ENV: str = "sandbox"

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

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
