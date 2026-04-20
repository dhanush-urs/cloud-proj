import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Only use standalone output for production builds to avoid issues in dev
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  // Ensure the tracing root is correctly set to the workspace root for docker context
  outputFileTracingRoot: path.join(__dirname, "../../"),
  // Proxy /api/v1/* to the backend API so browser-side relative fetches work.
  // This means client components can use fetch('/api/v1/...') without needing
  // NEXT_PUBLIC_API_BASE_URL to be set.
  async rewrites() {
    const apiBase =
      process.env.SERVER_API_BASE_URL?.replace(/\/api\/v1\/?$/, "") ||
      "http://api:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBase}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
