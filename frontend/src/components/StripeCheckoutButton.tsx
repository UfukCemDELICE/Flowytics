"use client";

import React, { useState } from "react";
import { useAuth } from "@clerk/nextjs";

interface Props {
  subscriptionStatus: string | null;
}

export function StripeCheckoutButton({ subscriptionStatus }: Props) {
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
          cancel_url: `${window.location.origin}/dashboard`,
        }),
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };


  const handlePortal = async () => {
    setLoading(true);
    try {
        const token = await getToken();
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/v1/stripe/create-portal-session`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        if (data.url) window.location.href = data.url;
    } catch (error) {
        console.error(error);
    } finally {
        setLoading(false);
    }
};
  if (subscriptionStatus === "active") {
    return (
        <div className="space-y-2">
            <div className="w-full text-center py-3 px-4 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm font-medium">
                ✓ Subscribed!
            </div>
            <button
                onClick={handlePortal}
                className="w-full bg-transparent border border-surface-border text-text-dim hover:bg-zinc-50 px-4 py-2 rounded-lg text-sm transition-all"
            >
                Manage Subscription
            </button>
        </div>
    );
}

  return (
    <button
      onClick={handleCheckout}
      disabled={loading}
      className="w-full bg-primary hover:bg-primary-hover text-white px-4 py-3 rounded-lg text-sm font-bold transition-all disabled:opacity-50"
    >
      {loading ? "Preparing..." : "Start Free Trial"}
    </button>
  );
}