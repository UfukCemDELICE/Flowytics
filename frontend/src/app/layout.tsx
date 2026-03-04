import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL('https://flowytics.io'),
  title: {
    default: "Flowytics | Agentic CFO for Pre-Seed & Seed Startups",
    template: "%s | Flowytics"
  },
  description: "Your accounting software has the data. You're missing the CFO. Agentic CFO for Pre-Seed & Seed Startups.",
  keywords: [
    "Agentic CFO", "Startup Finance", "Cash Flow Visibility", "Runway Forecasting",
    "Pre-Seed Startups", "Seed Startups", "Financial Planning", "Burn Rate"
  ],
  authors: [{ name: "Flowytics" }],
  creator: "Flowytics",
  publisher: "Flowytics",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://flowytics.io",
    siteName: "Flowytics",
    title: "Flowytics | Agentic CFO for Pre-Seed & Seed Startups",
    description: "Your accounting software has the data. You're missing the CFO. Agentic CFO for Pre-Seed & Seed Startups.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Flowytics" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Flowytics | Agentic CFO for Pre-Seed & Seed Startups",
    description: "Your accounting software has the data. You're missing the CFO. Agentic CFO for Pre-Seed & Seed Startups.",
    images: ["/og-image.png"],
    creator: "@flowytics",
  },
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="light" style={{ scrollBehavior: 'smooth' }}>
        <head>
          <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
        </head>
        <body
          className={`${inter.variable} ${jetbrainsMono.variable} bg-background-light text-text-dim font-display overflow-x-hidden antialiased`}
        >
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
