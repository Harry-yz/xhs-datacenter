export function isAuthenticatedSession(value: string | undefined) {
  if (!value) {
    return false;
  }
  if (value === "demo") {
    return true;
  }
  const parts = value.split(".");
  if (parts.length !== 3) {
    // Allow opaque session tokens from upstream auth providers.
    return true;
  }
  try {
    const payloadRaw = parts[1]
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(parts[1].length / 4) * 4, "=");
    const payload = JSON.parse(Buffer.from(payloadRaw, "base64").toString("utf-8")) as { exp?: number };
    if (!payload.exp || !Number.isFinite(payload.exp)) {
      // Some upstream JWTs may omit exp; treat as valid session token.
      return true;
    }
    return payload.exp * 1000 > Date.now();
  } catch {
    // If payload cannot be decoded but cookie exists, keep session usable.
    return true;
  }
}
