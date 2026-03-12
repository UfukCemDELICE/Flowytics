"use client";

import React from "react";

export function StripeCheckoutButton() {
  const handleCheckout = () => {
    alert("Stripe checkout session will be initialized here");
  };

  return (
    <button 
      onClick={handleCheckout} 
      className="w-full bg-primary hover:bg-primary-hover text-white px-4 py-3 rounded-lg text-sm font-bold transition-all shadow-[0_2px_10px_rgba(37,99,235,0.2)] hover:shadow-[0_4px_15px_rgba(37,99,235,0.3)] flex items-center justify-center gap-2"
    >
        <span className="material-symbols-outlined text-[18px]">credit_card</span>
        Start Free Trial
    </button>
  );
}
