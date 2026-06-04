import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { LogoLink } from "@/components/LogoLink";

export default async function Home() {
  const { userId } = await auth();

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-surface-border glass-nav">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LogoLink />
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a className="text-sm font-medium text-text-dim hover:text-primary transition-colors" href="#how-it-works">How It Works</a>
            <a className="text-sm font-medium text-text-dim hover:text-primary transition-colors" href="#features">Features</a>
            <a className="text-sm font-medium text-text-dim hover:text-primary transition-colors" href="#pricing">Pricing</a>
            <a className="text-sm font-medium text-text-dim hover:text-primary transition-colors" href="#faq">FAQ</a>
          </div>
          <div className="flex items-center gap-4">
            {userId ? (
              <>
                <Link className="hidden sm:block text-sm font-medium text-text-main hover:text-primary transition-colors" href="/dashboard">Dashboard</Link>
                <Link className="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded-lg text-sm font-bold transition-all shadow-[0_2px_10px_rgba(37,99,235,0.2)] hover:shadow-[0_4px_15px_rgba(37,99,235,0.3)]" href="/dashboard">
                  Go to Dashboard
                </Link>
              </>
            ) : (
              <>
                <Link className="hidden sm:flex text-sm font-bold text-text-main border border-surface-border hover:border-primary/50 bg-white px-5 py-2 rounded-lg transition-all items-center shadow-sm" href="/sign-in">
                  Sign In
                </Link>
                <Link className="bg-primary hover:bg-primary-hover text-white px-5 py-2 rounded-lg text-sm font-bold transition-all shadow-[0_2px_10px_rgba(37,99,235,0.2)] hover:shadow-[0_4px_15px_rgba(37,99,235,0.3)]" href="/sign-up">
                  Sign Up
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>
      
      <section className="relative pt-32 pb-20 px-6 overflow-hidden bg-gradient-to-b from-white to-blue-50/30">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-primary/5 rounded-full blur-[120px] pointer-events-none"></div>
        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
          <div className="flex flex-col gap-6 max-w-2xl relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 w-fit">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
              <span className="text-xs font-mono text-primary font-medium tracking-wide uppercase">Beta Access Open</span>
            </div>
            <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight leading-[1.1] text-text-main">
              Your accounting software has the data. <br/>
              <span className="text-text-dim font-normal">You&apos;re missing the</span> <span className="text-primary">CFO.</span>
            </h1>
            <p className="text-lg text-text-dim max-w-lg leading-relaxed">
              Stop flying blind. Flowytics turns your accounting data into actionable financial intelligence, delivered straight to Slack before you burn out.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 mt-4">
              <Link className="bg-primary hover:bg-primary-hover text-white px-8 py-3.5 rounded-lg text-base font-bold transition-all shadow-[0_4px_14px_rgba(37,99,235,0.3)] flex items-center justify-center gap-2" href={userId ? "/dashboard" : "/sign-up"}>
                {userId ? "Go to Dashboard" : "Sign Up Now"}
                <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
              </Link>
              <button className="px-8 py-3.5 rounded-lg text-base font-medium text-text-main border border-surface-border hover:border-primary hover:text-primary bg-white transition-colors flex items-center justify-center gap-2 group shadow-sm">
                <span className="material-symbols-outlined text-primary group-hover:scale-110 transition-transform">play_circle</span>
                See How It Works
              </button>
            </div>
          </div>
          <div className="relative w-full max-w-[500px] lg:max-w-none mx-auto transform hover:-translate-y-2 transition-transform duration-500 ease-out">
            <div className="bg-white border border-surface-border rounded-xl shadow-2xl overflow-hidden">
              <div className="bg-gray-50 px-4 py-3 border-b border-surface-border flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-400"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
                  <div className="w-3 h-3 rounded-full bg-green-400"></div>
                </div>
                <div className="mx-auto text-xs text-text-dim font-medium">#financial-updates</div>
              </div>
              <div className="p-6 flex flex-col gap-6 bg-white">
                <div className="flex gap-4">
                  <div className="w-10 h-10 rounded bg-primary flex items-center justify-center shrink-0 shadow-sm">
                    <span className="material-symbols-outlined text-white">smart_toy</span>
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-text-main">Flowytics AI</span>
                      <span className="px-1.5 py-0.5 rounded bg-gray-100 text-[10px] text-text-dim uppercase font-bold tracking-wider border border-gray-200">App</span>
                      <span className="text-xs text-text-dim">9:41 AM</span>
                    </div>
                    <p className="text-sm text-gray-600">
                      ⚠️ <strong className="text-text-main">Burn Rate Alert:</strong> Monthly spend is trending <span className="text-red-600 font-mono font-bold">+18%</span> above average.
                    </p>
                    <div className="mt-3 bg-white border border-surface-border rounded-lg p-4 relative overflow-hidden group shadow-sm">
                      <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500"></div>
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <div className="text-xs text-text-dim uppercase tracking-wider mb-1">Projected Runway</div>
                          <div className="text-2xl font-mono font-bold text-text-main">5.2 Months</div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-text-dim uppercase tracking-wider mb-1">Cash Balance</div>
                          <div className="text-lg font-mono font-bold text-text-main">$248,390</div>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs py-1 border-b border-gray-100">
                          <span className="text-gray-500">AWS Expenses</span>
                          <span className="font-mono text-red-600">+$2,400 (New)</span>
                        </div>
                        <div className="flex justify-between text-xs py-1 border-b border-gray-100">
                          <span className="text-gray-500">Payroll</span>
                          <span className="font-mono text-text-main">$45,000</span>
                        </div>
                      </div>
                      <div className="mt-4 flex gap-2">
                        <button className="bg-primary hover:bg-primary-hover text-white text-xs font-bold px-3 py-1.5 rounded shadow-sm transition-colors">
                          Analyze Spend
                        </button>
                        <button className="bg-gray-100 hover:bg-gray-200 text-text-main text-xs font-medium px-3 py-1.5 rounded border border-gray-200 transition-colors">
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="absolute -right-4 top-20 bg-white border border-surface-border p-3 rounded-lg shadow-xl flex items-center gap-3 animate-bounce hidden md:flex" style={{ animationDuration: '3s' }}>
              <div className="bg-green-100 p-1.5 rounded text-green-600">
                <span className="material-symbols-outlined text-sm">trending_up</span>
              </div>
              <div>
                <div className="text-[10px] text-text-dim uppercase">MRR Growth</div>
                <div className="text-sm font-mono font-bold text-text-main">+12.4%</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 border-t border-surface-border bg-background-dark">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-text-main">The Gap in Your Finance Stack</h2>
            <p className="text-text-dim max-w-2xl mx-auto">Accounting software looks backward. Consultants are too expensive. You need real-time intelligence.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white border border-surface-border p-8 rounded-2xl hover:border-primary/50 hover:shadow-lg transition-all group">
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-6 group-hover:bg-primary group-hover:text-white text-primary transition-colors">
                <span className="material-symbols-outlined text-[28px]">history</span>
              </div>
              <h3 className="text-xl font-bold text-text-main mb-2">Reactive Accounting</h3>
              <p className="text-text-dim leading-relaxed">Bookkeepers record history, they don&apos;t predict the future. By the time you get the P&amp;L, it&apos;s 20 days too late.</p>
            </div>
            <div className="bg-white border border-surface-border p-8 rounded-2xl hover:border-primary/50 hover:shadow-lg transition-all group">
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-6 group-hover:bg-primary group-hover:text-white text-primary transition-colors">
                <span className="material-symbols-outlined text-[28px]">monetization_on</span>
              </div>
              <h3 className="text-xl font-bold text-text-main mb-2">Expensive Consultants</h3>
              <p className="text-text-dim leading-relaxed">Fractional CFOs cost $5k/mo minimum for basic insights. Flowytics gives you the same answers instantly.</p>
            </div>
            <div className="bg-white border border-surface-border p-8 rounded-2xl hover:border-primary/50 hover:shadow-lg transition-all group">
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-6 group-hover:bg-primary group-hover:text-white text-primary transition-colors">
                <span className="material-symbols-outlined text-[28px]">grid_on</span>
              </div>
              <h3 className="text-xl font-bold text-text-main mb-2">Spreadsheet Hell</h3>
              <p className="text-text-dim leading-relaxed">Manual models break easily and are outdated instantly. Stop wasting weekends fixing broken formulas.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 px-6 relative bg-white" id="how-it-works">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between relative gap-12 md:gap-0">
            <div className="hidden md:block absolute top-12 left-[10%] right-[10%] h-[2px] bg-gradient-to-r from-surface-border via-primary/30 to-surface-border z-0"></div>
            <div className="relative z-10 flex flex-col items-center text-center max-w-[300px]">
              <div className="w-24 h-24 rounded-full bg-white border-2 border-surface-border flex items-center justify-center mb-6 shadow-lg relative group">
                <div className="absolute inset-0 bg-primary/10 rounded-full blur-xl opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <span className="material-symbols-outlined text-4xl text-text-main">link</span>
              </div>
              <h3 className="text-xl font-bold text-text-main mb-2">1. Connect Data</h3>
              <p className="text-sm text-text-dim">One-click integration with Accounting Software and Bank Accounts. Read-only access securely encrypted.</p>
            </div>
            <div className="relative z-10 flex flex-col items-center text-center max-w-[300px]">
              <div className="w-24 h-24 rounded-full bg-white border-2 border-primary flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(37,99,235,0.15)]">
                <span className="material-symbols-outlined text-4xl text-primary animate-pulse">psychology</span>
              </div>
              <h3 className="text-xl font-bold text-text-main mb-2">2. AI Analysis</h3>
              <p className="text-sm text-text-dim">Our models analyze cash flow patterns, categorize spend, and calculate real-time runway.</p>
            </div>
            <div className="relative z-10 flex flex-col items-center text-center max-w-[300px]">
              <div className="w-24 h-24 rounded-full bg-white border-2 border-surface-border flex items-center justify-center mb-6 shadow-lg relative group">
                <div className="absolute inset-0 bg-primary/10 rounded-full blur-xl opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <span className="material-symbols-outlined text-4xl text-text-main">notifications_active</span>
              </div>
              <h3 className="text-xl font-bold text-text-main mb-2">3. Receive Insights</h3>
              <p className="text-sm text-text-dim">Get proactive alerts via Slack or Email. Make decisions based on data, not gut feeling.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-background-dark border-y border-surface-border" id="features">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-3xl md:text-5xl font-bold mb-6 text-text-main">Financial Intelligence <br/>on <span className="text-primary">Autopilot</span></h2>
            <p className="text-xl text-text-dim max-w-2xl">Everything you need to manage burn, extend runway, and spot anomalies without lifting a finger.</p>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="p-8 rounded-2xl bg-white border border-surface-border hover:border-primary/30 hover:shadow-md transition-all group h-full">
              <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mb-6 text-primary">
                <span className="material-symbols-outlined">flight_takeoff</span>
              </div>
              <h3 className="text-2xl font-bold text-text-main mb-3">Runway Intelligence</h3>
              <p className="text-text-dim mb-6">Live forecast of your zero-cash date based on actual spending habits, not static spreadsheet assumptions.</p>
              <div className="h-32 bg-gray-50 rounded-lg border border-gray-100 p-4 flex items-end gap-2 relative overflow-hidden">
                <div className="w-full bg-blue-200 h-[40%] rounded-t"></div>
                <div className="w-full bg-blue-300 h-[60%] rounded-t"></div>
                <div className="w-full bg-blue-400 h-[50%] rounded-t"></div>
                <div className="w-full bg-blue-500 h-[30%] rounded-t"></div>
                <div className="w-full bg-primary h-[20%] rounded-t"></div>
                <div className="absolute top-2 left-2 text-xs font-mono text-text-dim/70">Cash Forecast</div>
              </div>
            </div>
            
            <div className="p-8 rounded-2xl bg-white border border-surface-border hover:border-primary/30 hover:shadow-md transition-all group h-full">
              <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mb-6 text-primary">
                <span className="material-symbols-outlined">local_fire_department</span>
              </div>
              <h3 className="text-2xl font-bold text-text-main mb-3">Burn Rate Monitoring</h3>
              <p className="text-text-dim mb-6">Instant alerts when monthly spending spikes above your moving average. Catch runway leaks early.</p>
              <div className="h-32 bg-gray-50 rounded-lg border border-gray-100 flex items-center justify-center relative overflow-hidden">
                <div className="absolute inset-0 bg-red-50"></div>
                <div className="text-center relative z-10">
                  <div className="text-xs text-text-dim mb-1">Current Burn</div>
                  <div className="text-3xl font-mono font-bold text-text-main">$42,500</div>
                  <div className="text-xs text-red-600 font-mono mt-1">▲ 12% vs last mo</div>
                </div>
              </div>
            </div>

            <div className="p-8 rounded-2xl bg-white border border-surface-border hover:border-primary/30 hover:shadow-md transition-all group h-full">
              <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mb-6 text-primary">
                <span className="material-symbols-outlined">radar</span>
              </div>
              <h3 className="text-2xl font-bold text-text-main mb-3">Anomaly Detection</h3>
              <p className="text-text-dim mb-6">AI automatically flags weird expenses, duplicate subscriptions, and unexpected vendor increases.</p>
              <div className="h-32 bg-gray-50 rounded-lg border border-gray-100 p-4 flex flex-col gap-2 justify-center">
                <div className="flex items-center gap-3 p-2 bg-white rounded border border-gray-200 shadow-sm">
                  <span className="material-symbols-outlined text-yellow-500 text-sm">warning</span>
                  <div className="text-xs text-text-dim flex-1">Duplicate Adobe Charge</div>
                  <div className="text-xs font-mono text-text-main">$54.99</div>
                </div>
                <div className="flex items-center gap-3 p-2 bg-white rounded border border-gray-200 shadow-sm">
                  <span className="material-symbols-outlined text-yellow-500 text-sm">warning</span>
                  <div className="text-xs text-text-dim flex-1">Unknown Vendor</div>
                  <div className="text-xs font-mono text-text-main">$120.00</div>
                </div>
              </div>
            </div>

            <div className="p-8 rounded-2xl bg-white border border-surface-border hover:border-primary/30 hover:shadow-md transition-all group h-full">
              <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mb-6 text-primary">
                <span className="material-symbols-outlined">mark_email_read</span>
              </div>
              <h3 className="text-2xl font-bold text-text-main mb-3">Monthly Briefing</h3>
              <p className="text-text-dim mb-6">A curated executive summary delivered to your inbox on the 1st of every month. Investor update ready.</p>
              <div className="h-32 bg-gray-50 rounded-lg border border-gray-100 p-6 flex flex-col gap-2 relative">
                <div className="w-2/3 h-2 bg-gray-300 rounded"></div>
                <div className="w-full h-2 bg-gray-200 rounded"></div>
                <div className="w-full h-2 bg-gray-200 rounded"></div>
                <div className="w-1/2 h-2 bg-gray-200 rounded"></div>
                <div className="absolute right-4 bottom-4 text-primary">
                  <span className="material-symbols-outlined text-4xl opacity-50">mail</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 px-6 bg-white">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-text-main">Why Founders Choose Flowytics</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[600px]">
              <thead>
                <tr>
                  <th className="p-4 text-sm font-medium text-text-dim w-1/4">Feature</th>
                  <th className="p-4 text-lg font-bold text-text-main bg-blue-50 border-t border-l border-r border-primary/20 rounded-t-xl w-1/4 text-center relative shadow-[0_-2px_10px_rgba(37,99,235,0.05)]">
                    <div className="absolute top-0 left-0 right-0 h-1 bg-primary"></div>
                    Flowytics
                  </th>
                  <th className="p-4 text-sm font-bold text-text-dim w-1/4 text-center">Fractional CFO</th>
                  <th className="p-4 text-sm font-bold text-text-dim w-1/4 text-center">Accounting Software</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                <tr className="border-b border-surface-border">
                  <td className="p-4 text-text-main font-medium">Real-time Insights</td>
                  <td className="p-4 text-center bg-blue-50/50 border-l border-r border-primary/20">
                    <span className="material-symbols-outlined text-primary font-bold">check_circle</span>
                  </td>
                  <td className="p-4 text-center text-text-dim">Monthly calls</td>
                  <td className="p-4 text-center text-text-dim">Historical only</td>
                </tr>
                <tr className="border-b border-surface-border">
                  <td className="p-4 text-text-main font-medium">Burn Rate Alerts</td>
                  <td className="p-4 text-center bg-blue-50/50 border-l border-r border-primary/20">
                    <span className="material-symbols-outlined text-primary font-bold">check_circle</span>
                  </td>
                  <td className="p-4 text-center text-text-dim"><span className="material-symbols-outlined text-gray-400">close</span></td>
                  <td className="p-4 text-center text-text-dim"><span className="material-symbols-outlined text-gray-400">close</span></td>
                </tr>
                <tr className="border-b border-surface-border">
                  <td className="p-4 text-text-main font-medium">Anomaly Detection</td>
                  <td className="p-4 text-center bg-blue-50/50 border-l border-r border-primary/20">
                    <span className="material-symbols-outlined text-primary font-bold">check_circle</span>
                  </td>
                  <td className="p-4 text-center text-text-dim">Manual Review</td>
                  <td className="p-4 text-center text-text-dim"><span className="material-symbols-outlined text-gray-400">close</span></td>
                </tr>
                <tr>
                  <td className="p-4 text-text-main font-medium">Cost</td>
                  <td className="p-4 text-center bg-blue-50/50 border-b border-l border-r border-primary/20 rounded-b-xl">
                    <span className="text-lg font-bold text-primary">$150/mo</span>
                  </td>
                  <td className="p-4 text-center text-text-dim">$5,000/mo+</td>
                  <td className="p-4 text-center text-text-dim">$80/mo</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="py-24 px-6 relative overflow-hidden bg-background-dark" id="pricing">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-primary/5 pointer-events-none"></div>
        <div className="max-w-lg mx-auto relative z-10">
          <div className="bg-white border border-surface-border rounded-2xl p-10 text-center shadow-xl relative">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-primary text-white text-sm font-bold px-4 py-1 rounded-full uppercase tracking-wide shadow-lg">
              Early Access Offer
            </div>
            <h2 className="text-2xl font-bold text-text-main mb-2">Startup Plan</h2>
            <p className="text-text-dim mb-8">Everything you need to master your runway.</p>
            <div className="flex items-center justify-center gap-3 mb-8">
              <span className="text-2xl text-gray-400 line-through decoration-red-500/50">$299</span>
              <span className="text-6xl font-black text-text-main">$150</span>
              <span className="text-text-dim self-end mb-2">/mo</span>
            </div>
            <ul className="text-left space-y-4 mb-10 max-w-xs mx-auto">
              <li className="flex items-center gap-3 text-text-main">
                <span className="material-symbols-outlined text-primary text-xl">check</span>
                Unlimited Bank Connections
              </li>
              <li className="flex items-center gap-3 text-text-main">
                <span className="material-symbols-outlined text-primary text-xl">check</span>
                Weekly Burn Reports
              </li>
              <li className="flex items-center gap-3 text-text-main">
                <span className="material-symbols-outlined text-primary text-xl">check</span>
                Slack &amp; Email Alerts
              </li>
              <li className="flex items-center gap-3 text-text-main">
                <span className="material-symbols-outlined text-primary text-xl">check</span>
                Priority Support
              </li>
            </ul>
            <button className="w-full bg-primary hover:bg-primary-hover text-white font-bold py-4 rounded-lg text-lg transition-all shadow-[0_4px_14px_rgba(37,99,235,0.3)] hover:shadow-[0_6px_20px_rgba(37,99,235,0.4)]">
              Start Your Free Trial
            </button>
            <p className="text-xs text-text-dim mt-4">No credit card required for 14-day trial.</p>
          </div>
        </div>
      </section>

      <section className="py-20 px-6 max-w-3xl mx-auto" id="faq">
        <h2 className="text-3xl font-bold text-center mb-12 text-text-main">Frequently Asked Questions</h2>
        <div className="space-y-4">
          <details className="group bg-white border border-surface-border rounded-lg shadow-sm">
            <summary className="flex justify-between items-center cursor-pointer p-6 list-none">
              <span className="font-medium text-lg text-text-main">Is my financial data secure?</span>
              <span className="transition group-open:rotate-180 text-text-dim">
                <span className="material-symbols-outlined">expand_more</span>
              </span>
            </summary>
            <div className="text-text-dim px-6 pb-6 pt-0 leading-relaxed">
              Absolutely. We use bank-level 256-bit encryption and partner with QuickBooks Online for read-only access. We never have the ability to move money or change records.
            </div>
          </details>
          <details className="group bg-white border border-surface-border rounded-lg shadow-sm">
            <summary className="flex justify-between items-center cursor-pointer p-6 list-none">
              <span className="font-medium text-lg text-text-main">How does Flowytics differ from Accounting Software?</span>
              <span className="transition group-open:rotate-180 text-text-dim">
                <span className="material-symbols-outlined">expand_more</span>
              </span>
            </summary>
            <div className="text-text-dim px-6 pb-6 pt-0 leading-relaxed">
              Accounting Software is for recording what happened in the past. Flowytics is for understanding what it means for your future. We sit on top of Accounting Software to give you insights.
            </div>
          </details>
          <details className="group bg-white border border-surface-border rounded-lg shadow-sm">
            <summary className="flex justify-between items-center cursor-pointer p-6 list-none">
              <span className="font-medium text-lg text-text-main">Can I cancel anytime?</span>
              <span className="transition group-open:rotate-180 text-text-dim">
                <span className="material-symbols-outlined">expand_more</span>
              </span>
            </summary>
            <div className="text-text-dim px-6 pb-6 pt-0 leading-relaxed">
              Yes, there are no long-term contracts. You can cancel your subscription at any time with a single click from your dashboard.
            </div>
          </details>
        </div>
      </section>

      <footer className="border-t border-surface-border bg-background-dark py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-2">
            <LogoLink />
          </div>
          <div className="flex flex-wrap justify-center gap-8 text-sm text-text-dim">
            <a className="hover:text-primary transition-colors" href="#">Privacy Policy</a>
            <a className="hover:text-primary transition-colors" href="#">Terms of Service</a>
            <a className="hover:text-primary transition-colors" href="#">Twitter</a>
            <a className="hover:text-primary transition-colors" href="#">LinkedIn</a>
          </div>
          <div className="text-sm text-text-dim/70">
            © 2026 Flowytics Inc.
          </div>
        </div>
      </footer>
    </>
  );
}
