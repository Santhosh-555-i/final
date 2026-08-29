import type { NextConfig } from "next";

const rawBackendUrl =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.RAILWAY_STATIC_URL ||
  process.env.RENDER_EXTERNAL_URL ||
  "http://127.0.0.1:8000";

const backendUrl = (
  rawBackendUrl.startsWith("http://") || rawBackendUrl.startsWith("https://")
    ? rawBackendUrl
    : `https://${rawBackendUrl}`
)
  .replace(/\/+$/, "")
  .replace(/\/api$/, "");

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
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/static/:path*",
        destination: `${backendUrl}/static/:path*`,
      },
    ];
  },
};

export default nextConfig;
