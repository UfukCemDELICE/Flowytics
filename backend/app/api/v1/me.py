from fastapi import APIRouter, Depends
from backend.app.auth import get_current_user

router = APIRouter(tags=["auth"])

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)) -> dict:
    """Test endpoint returning current user claims."""
    return user
