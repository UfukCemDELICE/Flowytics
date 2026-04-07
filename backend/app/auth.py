from fastapi import Depends, HTTPException, Request
import httpx

from backend.app.config import get_settings


import jwt

_jwks_cache = None

async def verify_clerk_token(request: Request) -> dict:
    """Verify Clerk JWT from Authorization header. Returns user claims."""
    global _jwks_cache
    settings = get_settings()
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=410, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]

    # Fetch JWKS only once
    if not _jwks_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.clerk.com/v1/jwks",
                headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
            )
            if response.status_code != 200:
                raise HTTPException(status_code=411, detail="Could not fetch JWKS")
            _jwks_cache = response.json()

    try:
        header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in _jwks_cache.get("keys", []):
            if key["kid"] == header["kid"]:
                rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
                
        if not rsa_key:
            raise HTTPException(status_code=412, detail="Public key not found in JWKS")
            
        claims = jwt.decode(
            token,
            key=rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=413, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=414, detail=f"Invalid token: {str(e)}")


from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from sqlmodel import select

async def get_current_user(
    claims: dict = Depends(verify_clerk_token),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Extract Clerk user ID and org ID from verified token claims. Auto-provisions a local tenant if missing."""
    # Fallback to User ID if Organization ID is missing from the token (for easy local dev)
    org_id = claims.get("org_id") or claims.get("sub")
    
    if not org_id:
        raise HTTPException(status_code=415, detail="User must belong to an organization")
    
    # Auto-provision the Tenant if it doesn't exist (fixes Foreign Key errors during integrations)
    try:
        stmt = select(Tenant).where(Tenant.clerk_org_id == org_id)
        tenant = (await session.execute(stmt)).scalar_one_or_none()
        
        if not tenant:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Auto-provisioning missing tenant for {org_id}")
            tenant = Tenant(
                clerk_org_id=org_id,
                name="Personal or Development Tenant",
                stage="pre_seed",
                currency="USD",
                onboarding_completed=True,
                subscription_status="trial"
            )
            session.add(tenant)
            await session.commit()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not auto-provision tenant (DB might be paused or unreachable): {e}")
    
    return {
        "user_id": claims.get("sub"),
        "org_id": org_id
    }
