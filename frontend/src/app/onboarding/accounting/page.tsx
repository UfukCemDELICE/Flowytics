"use client";

import { useAuth } from "@clerk/nextjs";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function AccountingPage() {
    const { getToken } = useAuth();
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleConnect = async () => {
        setLoading(true);
        try {
            const token = await getToken();
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/v1/quickbooks/auth`, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                }
            });
            
            if (!res.ok) {
                console.error("API Error", res.status, await res.text());
                setLoading(false);
                return;
            }

            const data = await res.json();
            if (data.auth_url) {
                window.location.href = data.auth_url;
            } else {
                console.error("No URL returned", data);
                setLoading(false);
            }
        } catch (error) {
            console.error(error);
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-zinc-950 text-white p-6">
            <div className="max-w-md text-center space-y-6">
                <h1 className="text-3xl font-bold">Connect Accounting Data</h1>
                <p className="text-zinc-400">
                    Connect your QuickBooks Online account so the AI CFO can analyze your expenses, revenue, and cash burn.
                </p>
                
                <div className="p-6 border border-zinc-800 rounded-lg bg-zinc-900/50">
                    {/* Placeholder for QBO icon */}
                    <div className="w-16 h-16 mx-auto bg-green-600 rounded-full flex items-center justify-center mb-4 text-2xl font-bold text-white tracking-tighter">qb</div>
                    <h3 className="text-xl font-semibold mb-2">QuickBooks Online</h3>
                    <p className="text-sm text-zinc-400 mb-6">Read-only access to your financial data.</p>
                    
                    <button 
                        onClick={handleConnect} 
                        disabled={loading}
                        className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-4 rounded-md transition-colors flex items-center justify-center disabled:opacity-50"
                    >
                        {loading ? "Connecting..." : "Connect QuickBooks"}
                    </button>
                </div>
                
                <button 
                    onClick={() => router.push("/onboarding/slack")}
                    disabled={loading}
                    className="w-full bg-transparent hover:bg-zinc-800 text-zinc-400 py-3 px-4 rounded-md transition-colors mt-4"
                >
                    Skip for now (Dev Mode)
                </button>
            </div>
        </div>
    );
}
