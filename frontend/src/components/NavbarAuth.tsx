"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";

interface NavbarAuthProps {
  initialUserId: string | null;
}

export function NavbarAuth({ initialUserId }: NavbarAuthProps) {
  const { userId, signOut, isLoaded } = useAuth();

  // Determine signed-in status: use active client session if loaded, fallback to server value otherwise
  const isSignedIn = isLoaded ? !!userId : !!initialUserId;

  if (isSignedIn) {
    return (
      <>
        <button
          onClick={() => signOut()}
          className="hidden sm:block text-sm font-medium text-text-main hover:text-primary transition-colors bg-transparent border-0 cursor-pointer p-0 font-sans font-semibold"
        >
          Sign Out
        </button>
        <Link 
          className="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded-lg text-sm font-bold transition-all shadow-[0_2px_10px_rgba(37,99,235,0.2)] hover:shadow-[0_4px_15px_rgba(37,99,235,0.3)]" 
          href="/dashboard"
        >
          Go to Dashboard
        </Link>
      </>
    );
  }

  return (
    <>
      <Link 
        className="hidden sm:flex text-sm font-bold text-text-main border border-surface-border hover:border-primary/50 bg-white px-5 py-2 rounded-lg transition-all items-center shadow-sm" 
        href="/sign-in"
      >
        Sign In
      </Link>
      <Link 
        className="bg-primary hover:bg-primary-hover text-white px-5 py-2 rounded-lg text-sm font-bold transition-all shadow-[0_2px_10px_rgba(37,99,235,0.2)] hover:shadow-[0_4px_15px_rgba(37,99,235,0.3)]" 
        href="/sign-up"
      >
        Sign Up
      </Link>
    </>
  );
}
