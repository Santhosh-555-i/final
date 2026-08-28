import type { NextConfig } from "next";

const rawBackendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const BACKEND_INTERNAL_URL = rawBackendUrl.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: false,
  // Standalone output for lightweight production Docker containers
  output: process.env.NEXT_OUTPUT_STANDALONE === "true" ? "standalone" : undefined,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_INTERNAL_URL}/api/:path*`,
      },
      {
        source: "/static/:path*",
        destination: `${BACKEND_INTERNAL_URL}/static/:path*`,
      },
    ];
  },
};

export default nextConfig;
