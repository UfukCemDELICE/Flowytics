"use client";

import React, { useState } from "react";
import { useAuth } from "@clerk/nextjs";

export function QuickBooksConnectButton({ connected }: { connected: boolean }) {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(false);

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
            console.error("API Error", res.status);
            setLoading(false);
            return;
        }

        const data = await res.json();
        if (data.auth_url) {
            window.location.href = data.auth_url;
        }
    } catch (error) {
        console.error(error);
        setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
        const token = await getToken();
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/v1/quickbooks/disconnect`, {
            method: "DELETE",
            headers: {
                Authorization: `Bearer ${token}`,
            }
        });
        
        if (res.ok) {
            window.location.reload();
        } else {
            console.error("API Error", res.status);
            setLoading(false);
        }
    } catch (error) {
        console.error(error);
        setLoading(false);
    }
  };

  if (connected) {
    return (
      <button 
        onClick={handleDisconnect}
        disabled={loading}
        className="bg-white border border-red-200 hover:border-red-500 hover:text-red-600 text-text-main px-4 py-2 rounded-lg text-sm font-bold transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50"
      >
        <span className="material-symbols-outlined text-[18px]">link_off</span>
        {loading ? "Disconnecting..." : "Disconnect QuickBooks"}
      </button>
    );
  }

  return (
    <button 
      onClick={handleConnect}
      disabled={loading}
      className="bg-white border border-surface-border hover:border-green-500 hover:text-green-600 text-text-main px-4 py-2 rounded-lg text-sm font-bold transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50"
    >
      <span className="material-symbols-outlined text-[18px]">api</span>
      {loading ? "Connecting..." : "Connect QuickBooks"}
    </button>
  );
}
