import { auth } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import NavBar from '../../../components/NavBar';
import RunwayCard from '../../../components/RunwayCard';
import RatioGrid from '../../../components/RatioGrid';
import AnomalyList from '../../../components/AnomalyList';
import type { ReportResponse } from '../../../types';

export default async function ReportsPage() {
  const { userId, getToken } = await auth();
  if (!userId) redirect('/sign-in');

  const token = await getToken();
  let report: ReportResponse | null = null;
  let error: string | null = null;

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/reports/financial`,
      { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }
    );
    if (res.ok) report = await res.json();
    else if (res.status === 403) error = 'QuickBooks not connected. Go to Dashboard to connect.';
    else error = 'Failed to load report.';
  } catch {
    error = 'Could not reach the backend. Is it running?';
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <NavBar />
      <main className="mx-auto max-w-5xl px-6 py-10 space-y-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Financial Report</h1>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {report && (
          <>
            {report.runway && <RunwayCard runway={report.runway} />}
            {report.ratios && (
              <section>
                <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Key Ratios</h2>
                <RatioGrid ratios={report.ratios} />
              </section>
            )}
            {report.anomalies && (
              <section>
                <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Anomalies</h2>
                <AnomalyList anomalies={report.anomalies.anomalies} />
              </section>
            )}
            {report.analysis && (
              <section>
                <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                  AI Analysis <span className="ml-2 text-xs text-zinc-400">({report.model_used})</span>
                </h2>
                <div className="rounded-xl border border-zinc-200 bg-white p-6 text-sm leading-relaxed text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
                  {report.analysis}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
