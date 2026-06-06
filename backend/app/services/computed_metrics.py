import logging
import json
from datetime import datetime, timezone
from sqlmodel import select

from backend.app.database import _get_engine
from backend.app.models.integration import Integration
from backend.app.models.financial_snapshot import FinancialSnapshot
from backend.app.models.computed_metric import ComputedMetric
from backend.app.utils import utc_now

from backend.app.tools.financial_summary import parse_qbo_to_financial_summary
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast

logger = logging.getLogger(__name__)

async def run_daily_computed_metrics() -> None:
    """Calculates and stores daily metrics for all active tenants."""
    logger.info("Starting daily computed metrics job.")
    
    _, session_factory = _get_engine()
    
    # 1. Fetch active/errored QBO integration tenant IDs
    async with session_factory() as session:
        stmt = select(Integration).where(
            Integration.provider == "quickbooks",
            Integration.sync_status.in_(["active", "error"])
        )
        res = await session.execute(stmt)
        integrations = res.scalars().all()
        tenant_ids = [integration.tenant_id for integration in integrations]
        
    logger.info(f"Found {len(tenant_ids)} active/errored QBO integration(s) to calculate metrics for.")
    
    success_count = 0
    failure_count = 0
    
    # 2. Process each tenant in a separate session/transaction
    for tenant_id in tenant_ids:
        logger.info(f"Calculating daily metrics for tenant {tenant_id}")
        try:
            async with session_factory() as session:
                # Load latest profit_loss and balance_sheet snapshots
                pl_stmt = select(FinancialSnapshot).where(
                    FinancialSnapshot.tenant_id == tenant_id,
                    FinancialSnapshot.data_type == "profit_loss"
                ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)
                
                bs_stmt = select(FinancialSnapshot).where(
                    FinancialSnapshot.tenant_id == tenant_id,
                    FinancialSnapshot.data_type == "balance_sheet"
                ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)
                
                pl_snap = (await session.execute(pl_stmt)).scalar_one_or_none()
                bs_snap = (await session.execute(bs_stmt)).scalar_one_or_none()
                
                if not pl_snap or not bs_snap:
                    logger.warning(f"Skipping tenant {tenant_id}: missing profit_loss or balance_sheet snapshot")
                    continue
                
                # Parse raw data into FinancialSummary
                summary = parse_qbo_to_financial_summary.invoke({
                    "pl_data": pl_snap.raw_data,
                    "bs_data": bs_snap.raw_data
                })
                
                if not summary.monthly_financials:
                    logger.warning(f"Skipping tenant {tenant_id}: parsed financial summary has no monthly financials")
                    continue
                
                # Run tools directly (not through the agent)
                burn_result = calculate_burn_rate.invoke({"summary": summary})
                runway_result = calculate_runway.invoke({"summary": summary, "burn_rate": burn_result})
                forecast_result = calculate_cash_forecast.invoke({"summary": summary})
                
                # Upsert results into computed_metrics table
                metrics_to_save = {
                    "burn_rate": burn_result,
                    "runway": runway_result,
                    "cash_forecast": forecast_result
                }
                
                period = datetime.now(timezone.utc).strftime("%Y-%m")
                
                for metric_type, result_model in metrics_to_save.items():
                    # Safely serialize Pydantic model with Decimals/dates to standard JSON-compatible dict
                    serialized_value = json.loads(result_model.model_dump_json())
                    
                    metric_stmt = select(ComputedMetric).where(
                        ComputedMetric.tenant_id == tenant_id,
                        ComputedMetric.metric_type == metric_type,
                        ComputedMetric.period == period
                    )
                    metric_res = await session.execute(metric_stmt)
                    existing_metric = metric_res.scalar_one_or_none()
                    
                    if existing_metric:
                        existing_metric.value = serialized_value
                        existing_metric.computed_at = utc_now()
                    else:
                        new_metric = ComputedMetric(
                            tenant_id=tenant_id,
                            metric_type=metric_type,
                            period=period,
                            value=serialized_value,
                            computed_at=utc_now()
                        )
                        session.add(new_metric)
                
                await session.commit()
                logger.info(f"Successfully calculated and saved metrics for tenant {tenant_id}")
                success_count += 1
                
        except Exception as e:
            logger.error(
                f"Failed to calculate metrics for tenant {tenant_id}: {e}",
                extra={"tenant_id": tenant_id, "error": str(e)},
                exc_info=True
            )
            failure_count += 1
            
    logger.info(f"Daily computed metrics job completed. Successes: {success_count}, Failures: {failure_count}")
