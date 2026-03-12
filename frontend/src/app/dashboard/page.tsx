import { auth } from "@clerk/nextjs/server";
import { UserButton } from "@clerk/nextjs";
import { StripeCheckoutButton } from "@/components/StripeCheckoutButton";
import { QuickBooksConnectButton } from "@/components/QuickBooksConnectButton";
import { SlackConnectButton } from "@/components/SlackConnectButton";
import { redirect } from "next/navigation";
import Link from "next/link";

export default async function DashboardPage() {
  const { userId } = await auth();

  if (!userId) {
    redirect("/sign-in");
  }

  return (
    <div className="min-h-screen bg-background-dark">
      {/* Navigation Bar */}
      <nav className="border-b border-surface-border glass-nav bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link href="/" className="text-2xl font-extrabold tracking-tight text-[#2962ff]">
              Flowytics
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <UserButton afterSignOutUrl="/" />
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="mb-10">
          <p className="text-lg text-text-dim">
            Complete your setup to start receiving CFO-level insights.
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Main Content Area: Integrations */}
          <div className="lg:col-span-2 space-y-6">
            <h2 className="text-2xl font-bold text-text-main mb-4">Integrations</h2>
            
            {/* QuickBooks Integration Card */}
            <div className="bg-white border border-surface-border p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group">
              <div className="absolute top-0 left-0 w-1 h-full bg-green-500"></div>
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-green-600 text-[28px]">account_balance</span>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-text-main mb-1">QuickBooks Online</h3>
                  <p className="text-sm text-text-dim mb-4">
                    Connect your accounting data securely. Flowytics only uses read-only access to analyze your financials.
                  </p>
                  <QuickBooksConnectButton />
                </div>
                <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-gray-100 border border-gray-200">
                  <span className="w-2 h-2 rounded-full bg-gray-400"></span>
                  <span className="text-xs font-medium text-text-dim">Not Connected</span>
                </div>
              </div>
            </div>

            {/* Slack Integration Card */}
            <div className="bg-white border border-surface-border p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group">
              <div className="absolute top-0 left-0 w-1 h-full bg-purple-500"></div>
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-purple-600 text-[28px]">forum</span>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-text-main mb-1">Slack Notifications</h3>
                  <p className="text-sm text-text-dim mb-4">
                    Get automated insights, burn rate alerts, and monthly CFO briefings delivered straight to your team&apos;s Slack.
                  </p>
                  <SlackConnectButton />
                </div>
                <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-gray-100 border border-gray-200">
                  <span className="w-2 h-2 rounded-full bg-gray-400"></span>
                  <span className="text-xs font-medium text-text-dim">Not Connected</span>
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar Area: Profile & Billing */}
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-text-main mb-4">Profile & Billing</h2>
            
            <div className="bg-white border border-surface-border p-6 rounded-2xl shadow-sm group relative overflow-hidden">
               <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-bl-full -z-10"></div>
              <h3 className="text-lg font-bold text-text-main mb-4">Subscription Plan</h3>
              <div className="mb-6">
                <div className="text-3xl font-black text-text-main flex items-baseline gap-1">
                  $150<span className="text-sm font-medium text-text-dim">/mo</span>
                </div>
                <p className="text-sm text-text-dim mt-1">Startup Plan (14-day free trial)</p>
              </div>
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm text-text-main">
                  <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                  Weekly Burn Reports
                </li>
                <li className="flex items-center gap-2 text-sm text-text-main">
                  <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                  AI Anomaly Detection
                </li>
                <li className="flex items-center gap-2 text-sm text-text-main">
                  <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                  Slack Briefings
                </li>
              </ul>
              <StripeCheckoutButton />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
