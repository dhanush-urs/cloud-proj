import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Only use standalone output for production builds to avoid issues in dev
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  // Ensure the tracing root is correctly set to the workspace root for docker context
  outputFileTracingRoot: path.join(__dirname, "../../"),
};

export default nextConfig;
