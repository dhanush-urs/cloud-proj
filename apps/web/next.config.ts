import type { NextConfig } from "next";

const nextConfig: any = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: require("path").join(__dirname, "../../"),
  experimental: {},
};

export default nextConfig;
