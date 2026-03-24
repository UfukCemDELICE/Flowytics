import json
import logging
from typing import Mapping

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.auth import get_current_user
from backend.app.integrations.stripe import create_checkout_session, verify_webhook
from backend.app.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.tenant import Tenant
from sqlmodel import select

router = APIRouter(tags=["stripe"])
logger = logging.getLogger(__name__)

class CheckoutRequest(BaseModel):
    tier: str
    success_url: str
    cancel_url: str

@router.post("/stripe/create-checkout-session")
async def api_create_checkout_session(
    request: CheckoutRequest,
    current_user: Mapping = Depends(get_current_user)
) -> dict:
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # We pass org_id so the webhook knows which tenant to update
    url = await create_checkout_session(
        clerk_org_id=org_id,
        tier=request.tier,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
    )
    return {"url": url}

@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session)
) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    try:
        event = verify_webhook(payload, sig_header)
    except Exception as e:
        logger.error(f"Webhook signature failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type")
    
    try:
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            clerk_org_id = session.get("metadata", {}).get("clerk_org_id")
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            
            if clerk_org_id:
                # Find the tenant
                stmt = select(Tenant).where(Tenant.clerk_org_id == clerk_org_id)
                result = await db.execute(stmt)
                tenant = result.scalar_one_or_none()
                
                if tenant:
                    tenant.stripe_customer_id = customer_id
                    tenant.stripe_subscription_id = subscription_id
                    tenant.subscription_status = "active"
                    db.add(tenant)
                    await db.commit()
                else:
                    logger.error(f"Tenant not found for clerk_org_id: {clerk_org_id}")

        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            customer_id = subscription.get("customer")
            status = subscription.get("status")
            
            # Map stripe status to our status
            mapped_status = "active"
            if status == "past_due":
                mapped_status = "past_due"
            elif status in ("canceled", "unpaid"):
                mapped_status = "cancelled"
            
            stmt = select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            result = await db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if tenant:
                tenant.subscription_status = mapped_status
                db.add(tenant)
                await db.commit()

        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            customer_id = invoice.get("customer")
            
            stmt = select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            result = await db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if tenant:
                tenant.subscription_status = "past_due"
                db.add(tenant)
                await db.commit()
                
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"error": "Processing failed"}

    return {"status": "success"}
