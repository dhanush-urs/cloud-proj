import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone output for production (Railway/Docker) — reduces image size significantly
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  // Ensure the tracing root is correctly set to the workspace root for docker context
  outputFileTracingRoot: path.join(__dirname, "../../"),

  // Proxy /api/v1/* to the backend so browser-side relative fetches work.
  // SERVER_API_BASE_URL is set to the internal Railway backend URL (e.g. http://api.railway.internal:8000)
  // or the public Railway URL (https://your-api.up.railway.app).
  // This means client-side code never needs to know the backend URL directly.
  async rewrites() {
    const apiBase =
      process.env.SERVER_API_BASE_URL?.replace(/\/api\/v1\/?$/, "") ||
      "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBase}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
