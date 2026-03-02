import stripe
from fastapi import HTTPException

from backend.app.config import get_settings

_PRICE_IDS: dict[str, str] = {
    "pro_monthly": "price_pro_monthly",  # Set real price ID from Stripe dashboard
}


def _client() -> stripe.Stripe:
    settings = get_settings()
    return stripe.Stripe(api_key=settings.stripe_secret_key)


async def create_checkout_session(
    clerk_user_id: str,
    tier: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return its URL."""
    price_id = _PRICE_IDS.get(tier)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {tier}")

    client = _client()
    session = client.checkout.sessions.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"clerk_user_id": clerk_user_id},
    )
    return session.url or ""


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature and return event dict."""
    settings = get_settings()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    return dict(event)
