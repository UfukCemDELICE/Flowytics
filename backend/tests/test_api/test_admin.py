import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from decimal import Decimal

from backend.app.main import app
from backend.app.database import get_session
from backend.app.models.integration import Integration

def test_clean_qbo_missing_confirm(client: TestClient):
    resp = client.post("/api/v1/admin/qbo/clean")
    assert resp.status_code == 400
    assert "Confirmation required" in resp.json()["detail"]

def test_clean_qbo_no_integration(client: TestClient):
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_res
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = client.post("/api/v1/admin/qbo/clean?confirm=true")
        assert resp.status_code == 404
        assert "No active QuickBooks integration found" in resp.json()["detail"]
    finally:
        del app.dependency_overrides[get_session]

@patch("backend.app.api.v1.admin.get_qbo_client")
@patch("fastapi.BackgroundTasks.add_task")
def test_seed_qbo_books_not_empty(mock_add_task, mock_get_qbo, client: TestClient):
    mock_session = AsyncMock()
    mock_integration = Integration(
        id="i-qbo-001",
        tenant_id="t-qbo-001",
        provider="quickbooks",
        provider_connection_id="realm-001"
    )
    
    mock_res_integ = MagicMock()
    mock_res_integ.scalars.return_value.first.return_value = mock_integration
    mock_session.execute.return_value = mock_res_integ
    
    # Mock QBO client and its reports
    mock_qb = MagicMock()
    mock_get_qbo.return_value = mock_qb
    
    # Mock get_report for P&L to return a non-empty report
    mock_qb.get_report.side_effect = [
        # ProfitAndLoss mock
        {
            "Columns": {
                "Column": [
                    {"ColTitle": "Account", "ColType": "Account"},
                    {"ColTitle": "May 2026", "ColType": "Month"}
                ]
            },
            "Rows": {"Row": [{"group": "Income", "Summary": {"ColData": [{"value": "Total Income"}, {"value": "1000.00"}]}}]}
        },
        # BalanceSheet mock
        {
            "Columns": {
                "Column": [
                    {"ColTitle": "Account", "ColType": "Account"},
                    {"ColTitle": "May 2026", "ColType": "Month"}
                ]
            },
            "Rows": {"Row": [{"group": "TotalAssets", "Summary": {"ColData": [{"value": "Total Bank Accounts"}, {"value": "50000.00"}]}}]}
        }
    ]
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = client.post("/api/v1/admin/qbo/seed")
        assert resp.status_code == 409
        assert "books not empty, run clean first" in resp.json()["detail"]
        mock_add_task.assert_not_called()
    finally:
        del app.dependency_overrides[get_session]

@patch("backend.app.api.v1.admin.get_qbo_client")
@patch("backend.app.api.v1.admin.Purchase")
@patch("backend.app.api.v1.admin.SalesReceipt")
@patch("fastapi.BackgroundTasks.add_task")
def test_seed_qbo_already_seeded(mock_add_task, mock_sales_receipt, mock_purchase, mock_get_qbo, client: TestClient):
    mock_session = AsyncMock()
    mock_integration = Integration(
        id="i-qbo-001",
        tenant_id="t-qbo-001",
        provider="quickbooks",
        provider_connection_id="realm-001"
    )
    
    mock_res_integ = MagicMock()
    mock_res_integ.scalars.return_value.first.return_value = mock_integration
    mock_session.execute.return_value = mock_res_integ
    
    # Mock QBO client and its reports
    mock_qb = MagicMock()
    mock_get_qbo.return_value = mock_qb
    
    # Mock get_report to return empty reports
    mock_qb.get_report.return_value = {}
    
    # Mock queries for idempotent safety
    mock_purchase.query.return_value = ["existing_purchase"]
    mock_sales_receipt.query.return_value = []
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = client.post("/api/v1/admin/qbo/seed")
        assert resp.status_code == 409
        assert "already seeded, run clean first" in resp.json()["detail"]
        mock_add_task.assert_not_called()
    finally:
        del app.dependency_overrides[get_session]

@patch("backend.app.api.v1.admin.get_qbo_client")
@patch("backend.app.api.v1.admin.Purchase")
@patch("backend.app.api.v1.admin.SalesReceipt")
@patch("fastapi.BackgroundTasks.add_task")
def test_seed_qbo_success(mock_add_task, mock_sales_receipt, mock_purchase, mock_get_qbo, client: TestClient):
    mock_session = AsyncMock()
    mock_integration = Integration(
        id="i-qbo-001",
        tenant_id="t-qbo-001",
        provider="quickbooks",
        provider_connection_id="realm-001"
    )
    
    mock_res_integ = MagicMock()
    mock_res_integ.scalars.return_value.first.return_value = mock_integration
    mock_session.execute.return_value = mock_res_integ
    
    # Mock QBO client and its reports
    mock_qb = MagicMock()
    mock_get_qbo.return_value = mock_qb
    
    # Mock get_report to return empty reports
    mock_qb.get_report.return_value = {}
    
    # Mock queries to return empty lists (not seeded yet)
    mock_purchase.query.return_value = []
    mock_sales_receipt.query.return_value = []
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = client.post("/api/v1/admin/qbo/seed")
        assert resp.status_code == 202
        assert resp.json() == {"message": "seed started"}
        mock_add_task.assert_called_once()
    finally:
        del app.dependency_overrides[get_session]
