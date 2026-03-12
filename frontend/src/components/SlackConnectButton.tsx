"use client";

import React from "react";

export function SlackConnectButton() {
  const handleConnect = () => {
    alert("Slack OAuth app authorization flow will be initialized here");
  };

  return (
    <button 
      onClick={handleConnect}
      className="bg-white border border-surface-border hover:border-purple-500 hover:text-purple-600 text-text-main px-4 py-2 rounded-lg text-sm font-bold transition-colors shadow-sm flex items-center gap-2"
    >
      <span className="material-symbols-outlined text-[18px]">add</span>
      Add to Slack
    </button>
  );
}
