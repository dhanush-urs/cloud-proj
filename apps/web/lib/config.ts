const isServer = typeof window === "undefined";
export const API_BASE_URL = isServer
  ? process.env.SERVER_API_BASE_URL || "http://api:8000/api/v1"
  : process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
