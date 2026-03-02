import type { RunwayResult } from '../types';

const ALERT_COLORS: Record<string, string> = {
  CRITICAL: 'bg-red-50 border-red-300 text-red-800 dark:bg-red-950 dark:border-red-700 dark:text-red-300',
  WARNING: 'bg-yellow-50 border-yellow-300 text-yellow-800 dark:bg-yellow-950 dark:border-yellow-700 dark:text-yellow-300',
  INFO: 'bg-blue-50 border-blue-300 text-blue-800 dark:bg-blue-950 dark:border-blue-700 dark:text-blue-300',
  OK: 'bg-green-50 border-green-300 text-green-800 dark:bg-green-950 dark:border-green-700 dark:text-green-300',
};

export default function RunwayCard({ runway }: { runway: RunwayResult }) {
  const alertClass = ALERT_COLORS[runway.alert.level] || '';
  const burnFmt = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(runway.monthly_burn_rate);

  return (
    <div className={`rounded-xl border p-6 ${alertClass}`}>
      <h3 className="text-sm font-medium uppercase tracking-wide opacity-70">Runway</h3>
      <p className="mt-1 text-4xl font-bold">
        {runway.runway_months !== null ? `${runway.runway_months.toFixed(1)} mo` : 'Profitable'}
      </p>
      <p className="mt-1 text-sm opacity-80">Burn rate: {burnFmt}/mo</p>
      <p className="mt-1 text-sm opacity-80">Trend: {runway.burn_trend}</p>
      {runway.cash_zero_date && (
        <p className="mt-1 text-sm opacity-80">Cash zero: {runway.cash_zero_date}</p>
      )}
      <p className="mt-3 text-sm font-medium">{runway.alert.message}</p>
    </div>
  );
}
