'use client';
import { UserButton } from '@clerk/nextjs';
import Link from 'next/link';

export default function NavBar() {
  return (
    <nav className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-white dark:bg-zinc-900 dark:border-zinc-800">
      <Link href="/dashboard" className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
        Flowytics
      </Link>
      <div className="flex items-center gap-4">
        <Link href="/dashboard" className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">Dashboard</Link>
        <Link href="/dashboard/reports" className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">Reports</Link>
        <Link href="/dashboard/cashflow" className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">Cash Flow</Link>
        <Link href="/dashboard/expenses" className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">Expenses</Link>
        <UserButton afterSignOutUrl="/sign-in" />
      </div>
    </nav>
  );
}
