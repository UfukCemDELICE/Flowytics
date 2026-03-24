import stripe
from fastapi import HTTPException

from backend.app.config import get_settings

_PRICE_IDS: dict[str, str] = {
    "pro_monthly": "price_pro_monthly",  # Set real price ID from Stripe dashboard
}


def _setup_stripe():
    settings = get_settings()
    stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_checkout_session(
    clerk_org_id: str,
    tier: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return its URL."""
    price_id = _PRICE_IDS.get(tier)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {tier}")

    _setup_stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"clerk_org_id": clerk_org_id},
    )
    return session.url or ""


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature and return event dict."""
    settings = get_settings()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    return dict(event)
