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
    <div className="min-h-screen bg-background-dark font-display text-text-main antialiased pb-20">
      <NavBar />
      <main className="mx-auto max-w-7xl px-6 pt-32">
        <div className="mb-12">
            <h1 className="text-4xl font-extrabold tracking-tight text-text-main">Dashboard</h1>
            <p className="text-lg text-text-dim mt-2 max-w-2xl">Financial intelligence and runway tracking at a glance.</p>
        </div>

        {!qbConnected && (
          <div className="mt-6 grid gap-6 md:grid-cols-3">
            {/* Accounting Card */}
            <div className="rounded-2xl border border-primary/20 bg-blue-50/50 p-8 shadow-sm relative overflow-hidden group flex flex-col h-full">
              <div className="absolute -right-20 -top-20 size-64 bg-primary/5 rounded-full blur-3xl group-hover:bg-primary/10 transition-colors pointer-events-none"></div>
              <div className="relative z-10 flex-1 flex flex-col">
                  <div className="size-14 rounded-2xl bg-white border border-primary/20 flex items-center justify-center text-primary mb-6 shadow-sm">
                      <span className="material-symbols-outlined text-[32px]">account_balance_wallet</span>
                  </div>
                  <h2 className="text-xl font-bold text-text-main mb-3">
                    Connect Accounting Software
                  </h2>
                  <p className="text-text-dim text-base mb-8 flex-1">
                    Flowytics needs access to your accounting data to generate real-time financial insights and runway forecasts.
                  </p>
                  <ConnectQBButton />
              </div>
            </div>

            {/* Bank Card */}
            <div className="rounded-2xl border border-surface-border bg-white p-8 shadow-sm relative overflow-hidden group flex flex-col h-full hover:border-primary/30 transition-all">
              <div className="relative z-10 flex-1 flex flex-col">
                  <div className="size-14 rounded-2xl bg-background-light border border-surface-border flex items-center justify-center text-text-main mb-6 shadow-sm transition-colors group-hover:text-primary group-hover:border-primary/30">
                      <span className="material-symbols-outlined text-[32px]">account_balance</span>
                  </div>
                  <h2 className="text-xl font-bold text-text-main mb-3">
                    Connect Bank Account
                  </h2>
                  <p className="text-text-dim text-base mb-8 flex-1">
                    Link your bank accounts for real-time cash flow monitoring and transaction tracking.
                  </p>
                  <button className="bg-white border border-surface-border hover:border-primary/50 hover:bg-background-light text-text-main px-6 py-3 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 group/btn w-full">
                    Connect Bank
                    <span className="material-symbols-outlined text-[18px] group-hover/btn:translate-x-1 transition-transform">arrow_forward</span>
                  </button>
              </div>
            </div>

            {/* Slack Card */}
            <div className="rounded-2xl border border-surface-border bg-white p-8 shadow-sm relative overflow-hidden group flex flex-col h-full hover:border-primary/30 transition-all">
              <div className="relative z-10 flex-1 flex flex-col">
                  <div className="size-14 rounded-2xl bg-background-light border border-surface-border flex items-center justify-center text-text-main mb-6 shadow-sm transition-colors group-hover:text-primary group-hover:border-primary/30">
                      <span className="material-symbols-outlined text-[32px]">forum</span>
                  </div>
                  <h2 className="text-xl font-bold text-text-main mb-3">
                    Connect Slack
                  </h2>
                  <p className="text-text-dim text-base mb-8 flex-1">
                    Get daily runway updates, burn rate alerts, and CFO insights directly in your workspace.
                  </p>
                  <button className="bg-white border border-surface-border hover:border-primary/50 hover:bg-background-light text-text-main px-6 py-3 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 group/btn w-full">
                    Connect Slack
                    <span className="material-symbols-outlined text-[18px] group-hover/btn:translate-x-1 transition-transform">arrow_forward</span>
                  </button>
              </div>
            </div>
          </div>
        )}

        {qbConnected && (
          <div className="mt-8 grid gap-8 sm:grid-cols-3">
            <DashCard icon="analytics" href="#" title="Financial Reports" desc="P&L, Balance Sheet, KPIs, and AI analysis" />
            <DashCard icon="timeline" href="#" title="Cash Flow" desc="Runway, burn rate, and 6-month projections" />
            <DashCard icon="receipt_long" href="#" title="Expenses" desc="Budget vs actual, anomaly detection" />
          </div>
        )}
      </main>
    </div>
  );
}

function DashCard({ icon, href, title, desc }: { icon: string, href: string; title: string; desc: string }) {
  return (
    <Link
      href={href}
      className="block rounded-2xl border border-surface-border bg-white p-8 transition-all hover:border-primary/30 hover:shadow-lg group h-full"
    >
      <div className="w-14 h-14 bg-blue-50 rounded-2xl flex items-center justify-center mb-6 text-primary group-hover:bg-primary group-hover:text-white transition-colors">
        <span className="material-symbols-outlined text-[32px]">{icon}</span>
      </div>
      <h3 className="text-2xl font-bold text-text-main mb-3">{title}</h3>
      <p className="text-text-dim leading-relaxed">{desc}</p>
    </Link>
  );
}

function ConnectQBButton() {
  return (
    <form
      action={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/quickbooks/authorize`}
      method="GET"
      className="w-full"
    >
      <button
        type="submit"
        className="bg-primary hover:bg-primary-hover text-white px-6 py-3 rounded-lg text-sm font-bold transition-all shadow-[0_4px_14px_rgba(37,99,235,0.3)] flex items-center justify-center gap-2 group/btn w-full"
      >
        Connect Accounting
        <span className="material-symbols-outlined text-[18px] group-hover/btn:translate-x-1 transition-transform">arrow_forward</span>
      </button>
    </form>
  );
}
