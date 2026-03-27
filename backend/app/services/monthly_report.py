import logging
import json
import os
from decimal import Decimal
from datetime import datetime, timezone
from sqlmodel import select
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from backend.app.database import _get_engine
from backend.app.models.tenant import Tenant
from backend.app.models.financial_snapshot import FinancialSnapshot
from backend.app.models.computed_metric import ComputedMetric
from backend.app.models.agent_run import AgentRun
from backend.app.integrations.slack import SlackClient

from backend.app.tools.financial_summary import parse_qbo_to_financial_summary
from backend.app.tools.monthly_report import generate_monthly_report_data, MonthlyReportData

logger = logging.getLogger(__name__)

async def run_monthly_reports(tenant_id: int | None = None):
    """
    CRON job that runs on the 1st of every month. 
    Can also be manually triggered for a specific tenant_id.
    """
    logger.info("Starting monthly CFO reports generation.")
    slack_client = SlackClient()
    
    # We use LangChain strictly for generation here (not LangGraph cyclic agent)
    llm = ChatAnthropic(model="claude-4-6-sonnet-latest", temperature=0.0)
    
    # Load system prompt
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent", "prompts", "report_generation.txt")
    system_prompt_text = ""
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt_text = f.read()
    system_message = SystemMessage(content=system_prompt_text)

    _, session_factory = _get_engine()
    async with session_factory() as session:
        # Fetch tenants
        stmt = select(Tenant).where(Tenant.slack_team_id != None)
        if tenant_id:
            stmt = stmt.where(Tenant.id == tenant_id)
            
        result = await session.execute(stmt)
        tenants = result.scalars().all()
        
        for tenant in tenants:
            try:
                # 1. Extract data
                pl_stmt = select(FinancialSnapshot).where(
                    FinancialSnapshot.tenant_id == tenant.id,
                    FinancialSnapshot.data_type == "profit_loss"
                ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)
                
                bs_stmt = select(FinancialSnapshot).where(
                    FinancialSnapshot.tenant_id == tenant.id,
                    FinancialSnapshot.data_type == "balance_sheet"
                ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)
                
                pl_snap = (await session.execute(pl_stmt)).scalar_one_or_none()
                bs_snap = (await session.execute(bs_stmt)).scalar_one_or_none()
                
                if not pl_snap or not bs_snap:
                    continue
                    
                raw_summary = parse_qbo_to_financial_summary.invoke({
                    "pl_data": pl_snap.raw_data,
                    "bs_data": bs_snap.raw_data
                })
                
                if not raw_summary.monthly_financials:
                    continue
                    
                # 2. Execute deterministic mathematical generation
                report_data: MonthlyReportData = generate_monthly_report_data.invoke({"summary": raw_summary})
                
                # Format exactly the sub-metrics we need for the LLM
                metrics_payload = report_data.model_dump_json()
                
                # 3. Request LLM Narrative summarization
                human_message = HumanMessage(content=metrics_payload)
                response = await llm.ainvoke([system_message, human_message])
                
                try:
                    llm_output = json.loads(response.content)
                    executive_summary = llm_output.get("executive_summary", "Financial summary unavailable.")
                    key_consideration = llm_output.get("key_consideration", "Continue monitoring runway closely.")
                except json.JSONDecodeError:
                    logger.error("Claude returned invalid JSON for CFO report.")
                    executive_summary = response.content
                    key_consideration = "Review full dashboard for details."

                # 4. Format Slack display UI
                ui_metrics = {
                    "mrr": report_data.fundraising.metrics.mrr,
                    "mrr_growth": report_data.fundraising.metrics.mrr_growth_rate,
                    "net_burn": report_data.burn.net_burn_monthly,
                    "runway_months": report_data.runway.runway_months,
                    "cash_balance": report_data.raw_summary.current_cash_balance
                }
                
                blocks = slack_client.format_monthly_cfo_report_block(
                    metrics=ui_metrics,
                    executive_summary=executive_summary,
                    key_consideration=key_consideration,
                    tenant_name="Your Startup"
                )
                
                # 5. Database Logging
                agent_run = AgentRun(
                    tenant_id=tenant.id,
                    trigger_type="scheduled_report",
                    status="completed",
                    model_used="claude-4-6-sonnet-latest",
                    output_result=ui_metrics
                )
                session.add(agent_run)
                await session.flush() # get ID
                
                metric = ComputedMetric(
                    tenant_id=tenant.id,
                    metric_type="monthly_report",
                    agent_run_id=agent_run.id,
                    value=json.loads(metrics_payload)
                )
                session.add(metric)
                await session.commit()
                
                # 6. Dispatch
                channel = tenant.slack_channel_id or "#general"
                fallback_text = f"Monthly CFO Report: Runway is {ui_metrics['runway_months']} months."
                
                success = await slack_client.send_message(channel, fallback_text, blocks=blocks)
                if success:
                    logger.info(f"Published monthly report to tenant {tenant.id}")
                else:
                    logger.warning(f"Failed to publish monthly report to {tenant.id}")
                
            except Exception as e:
                logger.error(f"Failed to generate monthly report for tenant {tenant.id}: {e}")
                await session.rollback()
