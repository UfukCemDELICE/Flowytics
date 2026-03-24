"use client";

import { useAuth } from "@clerk/nextjs";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SlackPage() {
    const { getToken } = useAuth();
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleConnect = async () => {
        setLoading(true);
        try {
            const token = await getToken();
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/v1/slack/install`, {
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
                console.error("No URL returned from slack install", data);
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
                <h1 className="text-3xl font-bold">Connect your workspace</h1>
                <p className="text-zinc-400">
                    Add Flowytics to your Slack workspace so you can chat with your AI CFO and receive daily executive briefings.
                </p>
                
                <div className="p-6 border border-zinc-800 rounded-lg bg-zinc-900/50">
                    <div className="w-16 h-16 mx-auto bg-white rounded-xl flex items-center justify-center mb-4">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/d/d5/Slack_icon_2019.svg" alt="Slack" className="w-10 h-10" />
                    </div>
                    <h3 className="text-xl font-semibold mb-2">Slack</h3>
                    <p className="text-sm text-zinc-400 mb-6">Install our bot to #general or #finance.</p>
                    
                    <button 
                        onClick={handleConnect} 
                        disabled={loading}
                        className="w-full bg-[#4A154B] hover:bg-[#3b113c] text-white font-semibold py-3 px-4 rounded-md transition-colors flex items-center justify-center disabled:opacity-50"
                    >
                        {loading ? "Redirecting..." : "Add to Slack"}
                    </button>
                </div>
                
                <button 
                    onClick={() => router.push("/dashboard")}
                    disabled={loading}
                    className="w-full bg-transparent hover:bg-zinc-800 text-zinc-400 py-3 px-4 rounded-md transition-colors mt-4"
                >
                    Complete Onboarding
                </button>
            </div>
        </div>
    );
}
