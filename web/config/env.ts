const publicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const internalApiBaseUrl = process.env.INTERNAL_API_BASE_URL ?? publicApiBaseUrl;

export const env = {
  apiBaseUrl: internalApiBaseUrl,
  publicApiBaseUrl,
  internalApiBaseUrl,
  useMockData: process.env.NEXT_PUBLIC_USE_MOCK_DATA !== "false",
  searchAutoPollEnabled: process.env.NEXT_PUBLIC_SEARCH_AUTO_POLL_ENABLED !== "false",
  unifiedLoginUrl: process.env.NEXT_PUBLIC_UNIFIED_LOGIN_URL ?? "",
  unifiedLoginNextParam: process.env.NEXT_PUBLIC_UNIFIED_LOGIN_NEXT_PARAM ?? "next",
} as const;
