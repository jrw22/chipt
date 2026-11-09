import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Playwright smoke tests run their own dev server (NEXT_DIST_DIR=.next-e2e) so they never
  // clash with a dev server you already have running on .next.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
