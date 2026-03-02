import type { RatioResult } from '../types';

function Metric({
  label,
  value,
  format = 'pct',
}: {
  label: string;
  value: number | null;
  format?: 'pct' | 'ratio' | 'currency';
}) {
  if (value === null) return null;
  let display = '';
  if (format === 'pct') display = `${(value * 100).toFixed(1)}%`;
  else if (format === 'ratio') display = `${value.toFixed(2)}x`;
  else
    display = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
    }).format(value);

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-4">
      <p className="text-xs text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{display}</p>
    </div>
  );
}

export default function RatioGrid({ ratios }: { ratios: RatioResult }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      <Metric label="Gross Margin" value={ratios.gross_margin} />
      <Metric label="Net Margin" value={ratios.net_margin} />
      <Metric label="Operating Margin" value={ratios.operating_margin} />
      <Metric label="Current Ratio" value={ratios.current_ratio} format="ratio" />
      <Metric label="Quick Ratio" value={ratios.quick_ratio} format="ratio" />
      <Metric label="Debt / Equity" value={ratios.debt_to_equity} format="ratio" />
      <Metric label="MoM Revenue Growth" value={ratios.mom_revenue_growth} />
      <Metric label="YoY Revenue Growth" value={ratios.yoy_revenue_growth} />
      {ratios.mrr !== null && <Metric label="MRR" value={ratios.mrr} format="currency" />}
      {ratios.arr !== null && <Metric label="ARR" value={ratios.arr} format="currency" />}
    </div>
  );
}
