import json
import logging
from datetime import datetime, timezone, timedelta
from cryptography.fernet import Fernet
from intuitlib.client import AuthClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from quickbooks import QuickBooks
from quickbooks.exceptions import QuickbooksException

from backend.app.config import get_settings
from backend.app.models.integration import Integration

settings = get_settings()
logger = logging.getLogger(__name__)

# We need a stable key for encrypting tokens. For now, use a fallback or an env var.
# But I will just mock/build the structure. Let's fix up later.
def get_fernet():
    """
    Returns a Fernet cipher for encrypting/decrypting QBO tokens.
    Prefers a dedicated FERNET_KEY env var; falls back to deriving from CLERK_SECRET_KEY.
    """
    if settings.FERNET_KEY:
        return Fernet(settings.FERNET_KEY.encode())
    
    # Fallback: derive from Clerk key (log warning — not recommended for production)
    import base64
    import hashlib
    logger.warning(
        "FERNET_KEY not set — deriving encryption key from CLERK_SECRET_KEY. "
        "Set FERNET_KEY for production use."
    )
    key = hashlib.sha256(settings.CLERK_SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def get_auth_client() -> AuthClient:
    return AuthClient(
        settings.QB_CLIENT_ID,
        settings.QB_CLIENT_SECRET,
        settings.QB_REDIRECT_URI,
        settings.QB_ENVIRONMENT,
    )

def generate_auth_url(state: str) -> str:
    from intuitlib.enums import Scopes
    auth_client = get_auth_client()
    return auth_client.get_authorization_url([Scopes.ACCOUNTING], state_token=state)

async def handle_callback(code: str, realm_id: str, tenant_id: str, session: AsyncSession) -> Integration:
    auth_client = get_auth_client()
    auth_client.get_bearer_token(code, realm_id=realm_id)
    
    fernet = get_fernet()
    tokens = {
        "access_token": auth_client.access_token,
        "refresh_token": auth_client.refresh_token,
        "expires_in": auth_client.expires_in,
        "x_refresh_token_expires_in": auth_client.x_refresh_token_expires_in,
        "realm_id": realm_id,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    encrypted = fernet.encrypt(json.dumps(tokens).encode()).decode()

    # Check if integration exists
    stmt = select(Integration).where(
        Integration.tenant_id == tenant_id,
        Integration.provider == "quickbooks"
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        integration.credentials_encrypted = encrypted
        integration.provider_connection_id = realm_id
        integration.sync_status = "active"
    else:
        integration = Integration(
            tenant_id=tenant_id,
            provider="quickbooks",
            provider_connection_id=realm_id,
            credentials_encrypted=encrypted,
            platform_name="QuickBooks Online",
            sync_status="active"
        )
        session.add(integration)
    
    await session.commit()
    await session.refresh(integration)
    return integration

async def auto_refresh_token(integration: Integration, session: AsyncSession) -> dict:
    if not integration.credentials_encrypted:
        raise TokenExpiredError("No credentials stored. Please reconnect QuickBooks.")
        
    fernet = get_fernet()
    tokens = json.loads(fernet.decrypt(integration.credentials_encrypted.encode()).decode())
    
    # Check expiry (simple heuristic or use intuitoauth2)
    # Intuit access tokens are valid for 60 minutes
    updated_at = datetime.fromisoformat(tokens["updated_at"])
    if datetime.now(timezone.utc) < updated_at + timedelta(minutes=50):
        # Still valid
        return tokens

    try:
        auth_client = get_auth_client()
        auth_client.refresh(refresh_token=tokens["refresh_token"])
    except Exception as e:
        logger.error(
            "QBO token refresh failed",
            extra={"tenant_id": integration.tenant_id, "provider": "quickbooks", "error_type": "token_refresh_failed"},
            exc_info=True,
        )
        integration.sync_status = "disconnected"
        integration.error_message = f"Token refresh failed: {str(e)}"
        await session.commit()
        raise TokenExpiredError(
            "QuickBooks connection expired. Please reconnect via the dashboard."
        ) from e
    
    tokens.update({
        "access_token": auth_client.access_token,
        "refresh_token": auth_client.refresh_token,
        "updated_at": datetime.now(timezone.utc).isoformat()
    })
    
    encrypted = fernet.encrypt(json.dumps(tokens).encode()).decode()
    integration.credentials_encrypted = encrypted
    await session.commit()
    
    return tokens


class IntegrationError(Exception):
    """Base class for integration-related errors."""
    pass


class TokenExpiredError(IntegrationError):
    """Raised when QBO OAuth tokens have expired and cannot be refreshed."""
    pass

async def get_qbo_client(realm_id: str, tenant_id: str, session: AsyncSession) -> QuickBooks:
    stmt = select(Integration).where(
        Integration.provider_connection_id == realm_id,
        Integration.provider == "quickbooks",
        Integration.tenant_id == tenant_id
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise IntegrationError(f"No QuickBooks integration found for realm_id {realm_id}")
        
    try:
        tokens = await auto_refresh_token(integration, session)
        auth_client = get_auth_client()
        auth_client.access_token = tokens["access_token"]
        auth_client.refresh_token = tokens["refresh_token"]
        
        qb = QuickBooks(
            auth_client=auth_client,
            refresh_token=tokens["refresh_token"],
            company_id=realm_id,
        )
        return qb
    except Exception as e:
        raise IntegrationError(f"Failed to initialize QuickBooks client: {str(e)}")

async def _fetch_report(realm_id: str, report_name: str, start_date: str, end_date: str, tenant_id: str, session: AsyncSession) -> dict:
    qb = await get_qbo_client(realm_id, tenant_id, session)
    try:
        report = qb.get_report(report_name, qs={"start_date": start_date, "end_date": end_date})
        return report
    except QuickbooksException as e:
        error_code = getattr(e, 'error_code', None) or getattr(e, 'status_code', None)
        if error_code in (401, '401', 'unauthorized'):
            raise TokenExpiredError(
                f"QuickBooks returned 401 for {report_name}. Please reconnect."
            ) from e
        raise IntegrationError(f"QuickBooks {report_name} request failed: {e.message}") from e


async def get_profit_and_loss(realm_id: str, start_date: str, end_date: str, tenant_id: str, session: AsyncSession) -> dict:
    return await _fetch_report(realm_id, "ProfitAndLoss", start_date, end_date, tenant_id, session)

async def get_balance_sheet(realm_id: str, start_date: str, end_date: str, tenant_id: str, session: AsyncSession) -> dict:
    return await _fetch_report(realm_id, "BalanceSheet", start_date, end_date, tenant_id, session)

async def get_cash_flow(realm_id: str, start_date: str, end_date: str, tenant_id: str, session: AsyncSession) -> dict:
    return await _fetch_report(realm_id, "CashFlow", start_date, end_date, tenant_id, session)

