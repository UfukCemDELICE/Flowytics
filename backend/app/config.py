from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Clerk
    clerk_secret_key: str

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # Anthropic
    anthropic_api_key: str

    # QuickBooks
    qb_client_id: str
    qb_client_secret: str
    qb_redirect_uri: str = "http://localhost:8000/api/v1/quickbooks/callback"
    qb_environment: str = "sandbox"

    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str

    # Slack
    slack_bot_token: str
    slack_signing_secret: str

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "flowytics"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
