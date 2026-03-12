"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function LogoLink() {
  const pathname = usePathname();

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (pathname === "/") {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <Link 
      href="/" 
      onClick={handleClick}
      className="text-4xl font-extrabold tracking-tight text-[#2962ff]"
    >
      Flowytics
    </Link>
  );
}
