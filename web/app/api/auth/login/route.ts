import { constants, publicEncrypt } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE, DEFAULT_LOCALE } from "@/config/i18n";

type LoginPayload = {
  email?: string;
  password?: string;
  next?: string;
};

type UpstreamLoginResponse = {
  code?: number;
  msg?: string;
  message?: string;
  detail?: string;
  success?: boolean;
  data?: {
    token?: string;
  };
};

export const runtime = "nodejs";

function getSafeNextPath(value: string | undefined) {
  if (!value || !value.startsWith("/")) {
    return `/${DEFAULT_LOCALE}/datacenter`;
  }
  return value;
}

function toPemPublicKey(rawValue: string) {
  const normalized = rawValue
    .replace(/-----BEGIN PUBLIC KEY-----/g, "")
    .replace(/-----END PUBLIC KEY-----/g, "")
    .replace(/\s+/g, "");
  if (!normalized) {
    throw new Error("empty rsa public key");
  }
  const wrapped = normalized.match(/.{1,64}/g)?.join("\n") ?? normalized;
  return `-----BEGIN PUBLIC KEY-----\n${wrapped}\n-----END PUBLIC KEY-----`;
}

function encryptPassword(password: string, publicKey: string, paddingMode: string) {
  const mode = paddingMode.trim().toUpperCase();
  if (mode === "OAEP_SHA256") {
    return publicEncrypt(
      {
        key: toPemPublicKey(publicKey),
        padding: constants.RSA_PKCS1_OAEP_PADDING,
        oaepHash: "sha256",
      },
      Buffer.from(password, "utf-8")
    ).toString("base64");
  }
  return publicEncrypt(
    {
      key: toPemPublicKey(publicKey),
      padding: constants.RSA_PKCS1_PADDING,
    },
    Buffer.from(password, "utf-8")
  ).toString("base64");
}

function getCookieMaxAgeFromToken(token: string) {
  const fallback = 60 * 60 * 24 * 7;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) {
      return fallback;
    }
    const payloadRaw = parts[1]
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(parts[1].length / 4) * 4, "=");
    const payload = JSON.parse(Buffer.from(payloadRaw, "base64").toString("utf-8")) as { exp?: number };
    if (!payload.exp || !Number.isFinite(payload.exp)) {
      return fallback;
    }
    const remaining = Math.floor(payload.exp - Date.now() / 1000);
    if (remaining <= 0) {
      return 60;
    }
    return Math.min(remaining, 60 * 60 * 24 * 30);
  } catch {
    return fallback;
  }
}

function shouldUseSecureCookie(request: NextRequest) {
  const forwardedProto = request.headers.get("x-forwarded-proto");
  if (forwardedProto) {
    const proto = forwardedProto.split(",")[0]?.trim().toLowerCase();
    return proto === "https";
  }
  return request.nextUrl.protocol === "https:";
}

export async function POST(request: NextRequest) {
  const upstreamBase = process.env.AUTH_UPSTREAM_BASE_URL ?? "http://94.74.101.163:28080";
  const authClientId = process.env.AUTH_CLIENT_ID ?? "portal-a";
  const authType = process.env.AUTH_TYPE ?? "EMAIL_PASSWORD";
  const authRsaPublicKey =
    process.env.AUTH_RSA_PUBLIC_KEY ??
    "MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAM51dgYtMyF+tTQt80sfFOpSV27a7t9uaUVeFrdGiVxscuizE7H8SMntYqfn9lp8a5GH5P1/GGehVjUD2gF/4kcCAwEAAQ==";
  const authRsaPadding = process.env.AUTH_RSA_PADDING ?? "PKCS1_v1_5";
  const payload = (await request.json().catch(() => ({}))) as LoginPayload;
  const email = String(payload.email ?? "").trim().toLowerCase();
  const password = String(payload.password ?? "");
  const next = getSafeNextPath(payload.next);

  if (!email || !password) {
    return NextResponse.json({ message: "email and password are required" }, { status: 400 });
  }

  try {
    const encryptedPassword = encryptPassword(password, authRsaPublicKey, authRsaPadding);
    const response = await fetch(`${upstreamBase.replace(/\/+$/, "")}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: authClientId,
        authType,
        email,
        password: encryptedPassword,
      }),
      cache: "no-store",
    });

    const backendPayload = (await response.json().catch(() => ({}))) as UpstreamLoginResponse;
    const token = backendPayload?.data?.token;
    const failedByPayload =
      backendPayload.success === false ||
      (typeof backendPayload.code === "number" && backendPayload.code !== 0);

    if (!response.ok || !token || failedByPayload) {
      const message = backendPayload.msg || backendPayload.detail || backendPayload.message || "invalid email or password";
      const status = failedByPayload && response.ok ? 401 : response.status || 401;
      return NextResponse.json({ message }, { status });
    }

    const output = NextResponse.json({ ok: true, next });
    output.cookies.set(SESSION_COOKIE, token, {
      httpOnly: true,
      path: "/",
      sameSite: "lax",
      secure: shouldUseSecureCookie(request),
      maxAge: getCookieMaxAgeFromToken(token),
    });
    return output;
  } catch {
    return NextResponse.json({ message: "auth service unavailable" }, { status: 503 });
  }
}
