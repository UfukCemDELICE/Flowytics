"use client";

import { useAuth } from "@clerk/nextjs";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function PaymentPage() {
    const { getToken } = useAuth();
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleCheckout = async () => {
        setLoading(true);
        try {
            const token = await getToken();
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/v1/stripe/create-checkout-session`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    tier: "pro_monthly",
                    success_url: `${window.location.origin}/onboarding/accounting`,
                    cancel_url: `${window.location.origin}/onboarding/payment`
                }),
            });
            
            if (!res.ok) {
                console.error("API Error", res.status, await res.text());
                setLoading(false);
                return;
            }

            const data = await res.json();
            if (data.url) {
                window.location.href = data.url;
            } else {
                console.error("No URL returned from checkout session", data);
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
                <h1 className="text-3xl font-bold">Start Your 14-Day Free Trial</h1>
                <p className="text-zinc-400">
                    Get full access to your personalized AI CFO. You won't be charged until the trial ends.
                </p>
                <button 
                    onClick={handleCheckout} 
                    disabled={loading}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-md transition-colors flex items-center justify-center disabled:opacity-50"
                >
                    {loading ? (
                        <>
                           <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                             <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                             <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                           </svg>
                           Preparing Secure Checkout...
                        </>
                    ) : "Start Free Trial →"}
                </button>
            </div>
        </div>
    );
}
