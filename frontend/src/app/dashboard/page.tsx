import { auth } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import NavBar from '../../components/NavBar';

export default async function DashboardPage() {
  const { userId, getToken } = await auth();
  if (!userId) redirect('/sign-in');

  const token = await getToken();
  let qbConnected = false;

  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/quickbooks/status`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (res.ok) {
      const data = await res.json();
      qbConnected = data.connected;
    }
  } catch {
    // Backend not running — show connect prompt
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <NavBar />
      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Dashboard</h1>

        {!qbConnected && (
          <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-6 dark:border-amber-700 dark:bg-amber-950">
            <h2 className="text-base font-semibold text-amber-900 dark:text-amber-200">
              Connect QuickBooks to get started
            </h2>
            <p className="mt-1 text-sm text-amber-700 dark:text-amber-400">
              Flowytics needs access to your QuickBooks data to generate financial insights.
            </p>
            <ConnectQBButton token={token!} />
          </div>
        )}

        {qbConnected && (
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <DashCard href="/dashboard/reports" title="Financial Report" desc="P&L, Balance Sheet, KPIs, and AI analysis" />
            <DashCard href="/dashboard/cashflow" title="Cash Flow" desc="Runway, burn rate, and 6-month projections" />
            <DashCard href="/dashboard/expenses" title="Expenses" desc="Budget vs actual, anomaly detection" />
          </div>
        )}
      </main>
    </div>
  );
}

function DashCard({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-zinc-200 bg-white p-6 transition hover:border-zinc-400 hover:shadow-sm dark:border-zinc-700 dark:bg-zinc-900 dark:hover:border-zinc-500"
    >
      <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{title}</h3>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{desc}</p>
    </Link>
  );
}

function ConnectQBButton({ token }: { token: string }) {
  return (
    <form
      action={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/quickbooks/authorize`}
      method="GET"
    >
      <button
        type="submit"
        className="mt-4 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700"
      >
        Connect QuickBooks
      </button>
    </form>
  );
}
