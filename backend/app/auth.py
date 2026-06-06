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
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]

    # Fetch JWKS only once
    if not _jwks_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.clerk.com/v1/jwks",
                headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Could not fetch JWKS")
            _jwks_cache = response.json()

    try:
        header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in _jwks_cache.get("keys", []):
            if key["kid"] == header["kid"]:
                rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
                
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Public key not found in JWKS")
            
        claims = jwt.decode(
            token,
            key=rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from sqlmodel import select

async def fetch_clerk_org_name(org_id: str, secret_key: str) -> str | None:
    if not org_id or not org_id.startswith("org_"):
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.clerk.com/v1/organizations/{org_id}",
                headers={"Authorization": f"Bearer {secret_key}"},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("name")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to fetch Clerk organization name for {org_id}: {e}")
    return None


async def fetch_clerk_user_name(user_id: str, secret_key: str) -> str | None:
    if not user_id:
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.clerk.com/v1/users/{user_id}",
                headers={"Authorization": f"Bearer {secret_key}"},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                first_name = data.get("first_name") or ""
                last_name = data.get("last_name") or ""
                name = f"{first_name} {last_name}".strip()
                if name:
                    return f"{name}'s Workspace"
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to fetch Clerk user details for {user_id}: {e}")
    return None


async def get_current_user(
    claims: dict = Depends(verify_clerk_token),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Extract Clerk user ID and org ID from verified token claims. Auto-provisions a local tenant if missing."""
    # Fallback to User ID if Organization ID is missing from the token (for easy local dev)
    org_id = claims.get("org_id") or claims.get("sub")
    
    if not org_id:
        raise HTTPException(status_code=401, detail="User must belong to an organization")
    
    # Auto-provision the Tenant if it doesn't exist (fixes Foreign Key errors during integrations)
    try:
        stmt = select(Tenant).where(Tenant.clerk_org_id == org_id)
        tenant = (await session.execute(stmt)).scalar_one_or_none()
        
        settings = get_settings()
        
        # Determine actual tenant name
        tenant_name = claims.get("org_name")
        if not tenant_name and isinstance(org_id, str) and org_id.startswith("org_"):
            tenant_name = await fetch_clerk_org_name(org_id, settings.CLERK_SECRET_KEY)
        
        sub_id = claims.get("sub")
        if not tenant_name and isinstance(sub_id, str):
            tenant_name = await fetch_clerk_user_name(sub_id, settings.CLERK_SECRET_KEY)
            
        if not tenant_name:
            tenant_name = "Personal or Development Tenant"
            
        if not tenant:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Auto-provisioning missing tenant for {org_id} with name {tenant_name}")
            tenant = Tenant(
                clerk_org_id=org_id,
                name=tenant_name,
                stage="pre_seed",
                currency="USD",
                onboarding_completed=True,
                subscription_status="trial"
            )
            session.add(tenant)
            await session.commit()
        elif tenant.name == "Personal or Development Tenant" and tenant_name != "Personal or Development Tenant":
            tenant.name = tenant_name
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
