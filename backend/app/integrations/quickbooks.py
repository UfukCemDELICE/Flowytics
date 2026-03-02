from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import httpx

from backend.app.config import get_settings
from backend.app.models.schemas import FinancialRow, FinancialStatement, QBTokenRecord

_QB_SANDBOX_BASE = "https://sandbox-quickbooks.api.intuit.com"
_QB_BASE = "https://quickbooks.api.intuit.com"
_QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
_QB_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
_SCOPES = "com.intuit.quickbooks.accounting"


class QuickBooksClient:
    """Async QuickBooks Online API client with auto token refresh."""

    def __init__(self, token: QBTokenRecord) -> None:
        self._token = token
        settings = get_settings()
        base = _QB_SANDBOX_BASE if settings.qb_environment == "sandbox" else _QB_BASE
        self._base_url = f"{base}/v3/company/{token.realm_id}"

    @staticmethod
    def get_authorization_url(state: str) -> str:
        settings = get_settings()
        params = (
            f"client_id={settings.qb_client_id}"
            f"&response_type=code"
            f"&scope={_SCOPES}"
            f"&redirect_uri={settings.qb_redirect_uri}"
            f"&state={state}"
        )
        return f"{_QB_AUTH_URL}?{params}"

    @staticmethod
    async def exchange_code(code: str, realm_id: str) -> QBTokenRecord:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _QB_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.qb_redirect_uri,
                },
                auth=(settings.qb_client_id, settings.qb_client_secret),
                headers={"Accept": "application/json"},
            )
        response.raise_for_status()
        data = response.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        return QBTokenRecord(
            user_id="",
            realm_id=realm_id,
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )

    async def _refresh_if_needed(self) -> None:
        if self._token.expires_at - datetime.now(timezone.utc) > timedelta(minutes=5):
            return
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _QB_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._token.refresh_token,
                },
                auth=(settings.qb_client_id, settings.qb_client_secret),
                headers={"Accept": "application/json"},
            )
        if response.status_code == 401:
            raise PermissionError("QuickBooks refresh token expired. User must reconnect.")
        response.raise_for_status()
        data = response.json()
        self._token.access_token = data["access_token"]
        self._token.refresh_token = data.get("refresh_token", self._token.refresh_token)
        self._token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

    async def _get(self, path: str, params: dict | None = None) -> dict:
        await self._refresh_if_needed()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {self._token.access_token}",
                    "Accept": "application/json",
                },
            )
        response.raise_for_status()
        return response.json()

    async def get_profit_and_loss(self, start_date: date, end_date: date) -> FinancialStatement:
        data = await self._get("reports/ProfitAndLoss", params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "summarize_column_by": "Month",
            "accounting_method": "Accrual",
        })
        return _normalize_report(data, "profit_loss")

    async def get_balance_sheet(self, start_date: date, end_date: date) -> FinancialStatement:
        data = await self._get("reports/BalanceSheet", params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "summarize_column_by": "Month",
        })
        return _normalize_report(data, "balance_sheet")

    async def get_cash_flow(self, start_date: date, end_date: date) -> FinancialStatement:
        data = await self._get("reports/CashFlow", params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "summarize_column_by": "Month",
        })
        return _normalize_report(data, "cash_flow")

    async def get_all_statements(self, months: int = 12) -> list[FinancialStatement]:
        end = date.today().replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        for _ in range(months - 1):
            start = (start - timedelta(days=1)).replace(day=1)
        return [
            await self.get_profit_and_loss(start, end),
            await self.get_balance_sheet(start, end),
            await self.get_cash_flow(start, end),
        ]

    @property
    def token(self) -> QBTokenRecord:
        return self._token


def _normalize_report(raw: dict, statement_type: str) -> FinancialStatement:
    header = raw.get("Header", {})
    company_name = header.get("ReportName", "Unknown Company")
    currency = header.get("Currency", "USD")
    period_start = date.fromisoformat(header.get("StartPeriod", "2024-01-01"))
    period_end = date.fromisoformat(header.get("EndPeriod", "2024-12-31"))

    columns = raw.get("Columns", {}).get("Column", [])
    period_labels: list[str] = []
    for col in columns:
        for m in col.get("MetaData", []):
            if m.get("Name") == "StartDate":
                period_labels.append(m["Value"][:7])
                break
        else:
            period_labels.append("")

    rows: list[FinancialRow] = []
    for section in raw.get("Rows", {}).get("Row", []):
        _extract_rows(section, period_labels, rows, "", "")

    return FinancialStatement(
        statement_type=statement_type,  # type: ignore[arg-type]
        company_name=company_name,
        currency=currency,
        period_start=period_start,
        period_end=period_end,
        rows=rows,
    )


def _extract_rows(
    node: dict,
    period_labels: list[str],
    acc: list[FinancialRow],
    category: str,
    subcategory: str,
) -> None:
    node_type = node.get("type", "")
    header = node.get("Header", {})
    group = header.get("ColData", [{}])[0].get("value", "") if header else ""
    new_category = category or group
    new_subcategory = group if category else subcategory

    if node_type == "Data":
        col_data = node.get("ColData", [])
        label = col_data[0].get("value", subcategory or category) if col_data else ""
        for idx, col in enumerate(col_data[1:], start=1):
            raw_val = col.get("value", "0") or "0"
            try:
                amount = Decimal(str(raw_val).replace(",", ""))
            except Exception:
                amount = Decimal("0")
            period = period_labels[idx - 1] if idx - 1 < len(period_labels) else ""
            if period:
                acc.append(FinancialRow(
                    category=new_category or label,
                    subcategory=label,
                    amount=amount,
                    period=period,
                ))

    for child in node.get("Rows", {}).get("Row", []):
        _extract_rows(child, period_labels, acc, new_category, new_subcategory)
