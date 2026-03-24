"use client";

import React, { useState } from "react";
import { useAuth } from "@clerk/nextjs";

export function StripeCheckoutButton() {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(false);

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
                success_url: `${window.location.origin}/dashboard`,
                cancel_url: `${window.location.origin}/dashboard`
            }),
        });
        
        if (!res.ok) {
            console.error("API Error", res.status);
            setLoading(false);
            return;
        }

        const data = await res.json();
        if (data.url) {
            window.location.href = data.url;
        }
    } catch (error) {
        console.error(error);
        setLoading(false);
    }
  };

  return (
    <button 
      onClick={handleCheckout} 
      disabled={loading}
      className="w-full bg-primary hover:bg-primary-hover text-white px-4 py-3 rounded-lg text-sm font-bold transition-all shadow-[0_2px_10px_rgba(37,99,235,0.2)] hover:shadow-[0_4px_15px_rgba(37,99,235,0.3)] flex items-center justify-center gap-2 disabled:opacity-50"
    >
        {loading ? (
             <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                 <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                 <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
             </svg>
        ) : (
             <span className="material-symbols-outlined text-[18px]">credit_card</span>
        )}
        {loading ? "Preparing..." : "Start Free Trial"}
    </button>
  );
}
