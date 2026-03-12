"use client";

import React from "react";

export function QuickBooksConnectButton() {
  const handleConnect = () => {
    alert("QuickBooks connection flow will be initialized here (Codat Link)");
  };

  return (
    <button 
      onClick={handleConnect}
      className="bg-white border border-surface-border hover:border-green-500 hover:text-green-600 text-text-main px-4 py-2 rounded-lg text-sm font-bold transition-colors shadow-sm flex items-center gap-2"
    >
      <span className="material-symbols-outlined text-[18px]">api</span>
      Connect QuickBooks
    </button>
  );
}
