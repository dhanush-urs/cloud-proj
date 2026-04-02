import type { NextConfig } from "next";

const nextConfig: any = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    outputFileTracingRoot: require("path").join(__dirname, "../../"),
  },
};

export default nextConfig;
