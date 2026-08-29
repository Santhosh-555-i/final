import type { NextConfig } from "next";

const rawBackendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const cleanBackendUrl = rawBackendUrl.replace(/\/+$/, "").replace(/\/api$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: false,
  trailingSlash: false,
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${cleanBackendUrl}/api/:path*`,
      },
      {
        source: "/static/:path*",
        destination: `${cleanBackendUrl}/static/:path*`,
      },
    ];
  },
};

export default nextConfig;
