const isServer = typeof window === "undefined";

// Determine API URL based on environment and runtime context (Server vs Browser)
const serverApiUrl = process.env.SERVER_API_BASE_URL || "http://api:8000/api/v1";
const clientApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export const API_BASE_URL = (isServer ? serverApiUrl : clientApiUrl).replace(/\/$/, "");
