export const env = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1",
  useMockData: process.env.NEXT_PUBLIC_USE_MOCK_DATA !== "false",
  unifiedLoginUrl: process.env.NEXT_PUBLIC_UNIFIED_LOGIN_URL ?? "",
  unifiedLoginNextParam: process.env.NEXT_PUBLIC_UNIFIED_LOGIN_NEXT_PARAM ?? "next",
} as const;
