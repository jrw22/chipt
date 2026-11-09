import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { ApiStatusBanner } from "@/components/api-status-banner";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Chipt", template: "%s · Chipt" },
  description: "All your race results in one place, and how you're improving over time.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning: next-themes sets the theme class before React hydrates.
    // Font variables go on <html> because globals.css applies `font-sans` there (--font-sans -> --font-geist-sans).
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body className="min-h-dvh antialiased">
        <Providers>
          <SiteHeader />
          <ApiStatusBanner />
          <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
