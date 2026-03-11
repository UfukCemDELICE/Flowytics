from fastapi import Depends, HTTPException, Request
import httpx

from backend.app.config import get_settings


async def verify_clerk_token(request: Request) -> dict:
    """Verify Clerk JWT from Authorization header. Returns user claims."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.clerk.com/v1/sessions/verify",
            headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
            params={"token": token},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")

    return response.json()


async def get_current_user(claims: dict = Depends(verify_clerk_token)) -> dict:
    """Extract Clerk user ID and org ID from verified token claims."""
    org_id = claims.get("org_id")
    if not org_id:
        raise HTTPException(status_code=401, detail="User must belong to an organization")
    
    return {
        "user_id": claims["sub"],
        "org_id": org_id
    }
