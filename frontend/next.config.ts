import type { NextConfig } from "next";

const rawBackendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const BACKEND_INTERNAL_URL = rawBackendUrl.replace(/\/+$/, "");

const isExport = process.env.NEXT_EXPORT === "true" || process.env.GITHUB_PAGES === "true";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  output: isExport ? "export" : (process.env.NEXT_OUTPUT_STANDALONE === "true" ? "standalone" : undefined),
  basePath: basePath || undefined,
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  ...(isExport ? {} : {
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
  }),
};

export default nextConfig;
