import { auth } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import NavBar from '../../../components/NavBar';
import AnomalyList from '../../../components/AnomalyList';
import type { BudgetResult, AnomalyResult } from '../../../types';

const ALERT_COLORS: Record<string, string> = {
  CRITICAL: 'text-red-700 dark:text-red-400',
  WARNING: 'text-yellow-700 dark:text-yellow-400',
  OK: 'text-green-700 dark:text-green-400',
};

export default async function ExpensesPage() {
  const { userId, getToken } = await auth();
  if (!userId) redirect('/sign-in');

  const token = await getToken();
  let budget: BudgetResult | null = null;
  let anomalies: AnomalyResult | null = null;
  let summary = '';
  let error: string | null = null;

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses/summary`,
      { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }
    );
    if (res.ok) {
      const data = await res.json();
      budget = data.budget;
      anomalies = data.anomalies;
      summary = data.summary;
    } else if (res.status === 403) {
      error = 'QuickBooks not connected.';
    } else {
      error = 'Failed to load expense data.';
    }
  } catch {
    error = 'Could not reach the backend.';
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <NavBar />
      <main className="mx-auto max-w-5xl px-6 py-10 space-y-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Expenses</h1>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {budget && budget.alerts.length > 0 && (
          <ul className="space-y-2">
            {budget.alerts.map((a, i) => (
              <li key={i} className="rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-700 dark:bg-yellow-950 dark:text-yellow-300">
                {a}
              </li>
            ))}
          </ul>
        )}

        {budget && budget.categories.length > 0 && (
          <section>
            <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Category Breakdown</h2>
            <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
              <table className="w-full text-sm">
                <thead className="bg-zinc-100 dark:bg-zinc-800 text-xs uppercase text-zinc-500 dark:text-zinc-400">
                  <tr>
                    <th className="px-4 py-3 text-left">Category</th>
                    <th className="px-4 py-3 text-right">Actual</th>
                    <th className="px-4 py-3 text-right">MoM</th>
                    <th className="px-4 py-3 text-right">vs Budget</th>
                    <th className="px-4 py-3 text-left">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                  {budget.categories.map((c) => (
                    <tr key={c.category} className="bg-white dark:bg-zinc-900">
                      <td className="px-4 py-3 font-medium text-zinc-900 dark:text-zinc-100">{c.category}</td>
                      <td className="px-4 py-3 text-right text-zinc-600 dark:text-zinc-400">
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(c.actual)}
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-600 dark:text-zinc-400">
                        {c.mom_growth !== null ? `${c.mom_growth > 0 ? '+' : ''}${c.mom_growth.toFixed(1)}%` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-600 dark:text-zinc-400">
                        {c.budget > 0 ? `${c.variance_pct > 0 ? '+' : ''}${c.variance_pct.toFixed(1)}%` : '—'}
                      </td>
                      <td className={`px-4 py-3 font-medium ${ALERT_COLORS[c.alert]}`}>{c.alert}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {anomalies && (
          <section>
            <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Anomalies</h2>
            <AnomalyList anomalies={anomalies.anomalies} />
          </section>
        )}

        {summary && (
          <section>
            <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">AI Summary</h2>
            <div className="rounded-xl border border-zinc-200 bg-white p-6 text-sm leading-relaxed text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
              {summary}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
