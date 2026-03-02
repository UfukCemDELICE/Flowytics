export interface RunwayAlert {
  level: 'CRITICAL' | 'WARNING' | 'INFO' | 'OK';
  message: string;
}

export interface RunwayResult {
  monthly_burn_rate: number;
  runway_months: number | null;
  weighted_burn_rate: number;
  burn_trend: 'increasing' | 'stable' | 'decreasing';
  cash_zero_date: string | null;
  alert: RunwayAlert;
}

export interface RatioResult {
  gross_margin: number | null;
  net_margin: number | null;
  operating_margin: number | null;
  current_ratio: number | null;
  quick_ratio: number | null;
  debt_to_equity: number | null;
  mom_revenue_growth: number | null;
  yoy_revenue_growth: number | null;
  revenue_per_employee: number | null;
  arr: number | null;
  mrr: number | null;
  net_revenue_retention: number | null;
  period: string;
}

export interface BudgetCategory {
  category: string;
  actual: number;
  budget: number;
  variance_pct: number;
  mom_growth: number | null;
  expense_to_revenue_pct: number | null;
  alert: 'CRITICAL' | 'WARNING' | 'OK';
}

export interface BudgetResult {
  categories: BudgetCategory[];
  top5_by_spend: string[];
  total_expense_mom_growth: number | null;
  alerts: string[];
}

export interface AnomalyItem {
  category: string;
  period: string;
  value: number;
  z_score: number;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  reason: string;
}

export interface AnomalyResult {
  anomalies: AnomalyItem[];
}

export interface ReportResponse {
  user_id: string;
  report_type: string;
  ratios: RatioResult | null;
  runway: RunwayResult | null;
  budget: BudgetResult | null;
  anomalies: AnomalyResult | null;
  analysis: string;
  model_used: string;
  discrepancies: unknown[];
  generated_at: string;
}
