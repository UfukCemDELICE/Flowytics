import { auth } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import NavBar from '../../../components/NavBar';
import RunwayCard from '../../../components/RunwayCard';
import type { RunwayResult } from '../../../types';

export default async function CashFlowPage() {
  const { userId, getToken } = await auth();
  if (!userId) redirect('/sign-in');

  const token = await getToken();
  let runway: RunwayResult | null = null;
  let analysis = '';
  let error: string | null = null;

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/cashflow/runway`,
      { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }
    );
    if (res.ok) {
      const data = await res.json();
      runway = data.runway;
      analysis = data.analysis;
    } else if (res.status === 403) {
      error = 'QuickBooks not connected.';
    } else {
      error = 'Failed to load cash flow data.';
    }
  } catch {
    error = 'Could not reach the backend.';
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <NavBar />
      <main className="mx-auto max-w-5xl px-6 py-10 space-y-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Cash Flow</h1>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {runway && <RunwayCard runway={runway} />}

        {analysis && (
          <section>
            <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Forecast Narrative</h2>
            <div className="rounded-xl border border-zinc-200 bg-white p-6 text-sm leading-relaxed text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
              {analysis}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
