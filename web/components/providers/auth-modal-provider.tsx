"use client";

import {
  createContext,
  type FormEvent,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import type { Locale } from "@/config/i18n";

type AuthModalContextValue = {
  authenticated: boolean;
  openAuthModal: (options?: { next?: string }) => void;
  closeAuthModal: () => void;
  logout: () => Promise<void>;
};

const AuthModalContext = createContext<AuthModalContextValue | null>(null);

export function useAuthModal() {
  const context = useContext(AuthModalContext);
  if (!context) {
    throw new Error("useAuthModal must be used within AuthModalProvider");
  }
  return context;
}

type AuthTab = "login" | "register";

export function AuthModalProvider({
  children,
  locale,
  initialAuthenticated,
}: {
  children: ReactNode;
  locale: Locale;
  initialAuthenticated: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const isZh = locale === "zh";

  const [authenticated, setAuthenticated] = useState(initialAuthenticated);
  const [open, setOpen] = useState(false);
  const [nextPath, setNextPath] = useState<string>("");
  const [tab, setTab] = useState<AuthTab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setAuthenticated(initialAuthenticated);
  }, [initialAuthenticated]);

  const openAuthModal = useCallback(
    (options?: { next?: string }) => {
      setError("");
      setTab("login");
      setNextPath(options?.next || pathname || `/${locale}/datacenter`);
      setOpen(true);
    },
    [locale, pathname]
  );

  const closeAuthModal = useCallback(() => {
    setOpen(false);
    setError("");
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // ignore network errors and still clear local state
    }
    setAuthenticated(false);
    router.refresh();
  }, [router]);

  useEffect(() => {
    if (authenticated) {
      return;
    }
    const current = new URLSearchParams(window.location.search);
    if (current.get("auth") !== "1") {
      return;
    }
    const next = current.get("next") || pathname || `/${locale}/datacenter`;
    current.delete("auth");
    current.delete("next");
    const query = current.toString();
    const cleaned = query ? `${pathname}?${query}` : pathname;
    router.replace(cleaned);
    openAuthModal({ next });
  }, [authenticated, locale, openAuthModal, pathname, router]);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError(isZh ? "请填写邮箱和密码" : "Please enter email and password");
      return;
    }
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password,
          next: nextPath,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        message?: string;
        next?: string;
      };
      if (!response.ok) {
        setError(payload.message || (isZh ? "登录失败，请检查账号密码" : "Login failed. Check credentials."));
        return;
      }
      setAuthenticated(true);
      setOpen(false);
      setPassword("");
      const target = payload.next || nextPath || pathname || `/${locale}/datacenter`;
      router.push(target);
      router.refresh();
    } catch {
      setError(isZh ? "网络异常，请稍后重试" : "Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const texts = useMemo(
    () => ({
      title: isZh ? "创建账号或登录" : "Create account or sign in",
      loginTitle: isZh ? "使用邮箱登录" : "Sign in with email",
      registerTitle: isZh ? "注册（暂未开放）" : "Register (Coming soon)",
      google: isZh ? "使用 Google 登录" : "Continue with Google",
      or: "or",
      email: isZh ? "邮箱" : "Email",
      password: isZh ? "密码" : "Password",
      login: isZh ? "登录" : "Login",
      register: isZh ? "注册" : "Register",
      forgot: isZh ? "忘记密码" : "Forgot password",
      disabledHint: isZh ? "当前仅开放管理员账号登录" : "Only admin account login is enabled now",
      agree: isZh
        ? "继续即表示您同意我们的服务条款并确认我们的隐私政策。"
        : "By continuing you agree to our Terms of Service and Privacy Policy.",
    }),
    [isZh]
  );

  const contextValue = useMemo<AuthModalContextValue>(
    () => ({
      authenticated,
      openAuthModal,
      closeAuthModal,
      logout,
    }),
    [authenticated, closeAuthModal, logout, openAuthModal]
  );

  return (
    <AuthModalContext.Provider value={contextValue}>
      {children}
      {open ? (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/42 p-4">
          <section className="w-full max-w-[560px] rounded-[28px] border border-border/35 bg-[linear-gradient(180deg,rgba(255,249,245,0.98),rgba(255,246,242,0.95))] p-6 shadow-2xl dark:bg-[linear-gradient(180deg,rgba(35,30,40,0.95),rgba(33,28,39,0.94))]">
            <div className="flex items-start justify-between">
              <h2 className="text-2xl font-semibold text-foreground">{texts.title}</h2>
              <button
                aria-label={isZh ? "关闭" : "Close"}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full text-foreground/60 transition hover:bg-foreground/10 hover:text-foreground"
                onClick={closeAuthModal}
                type="button"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <button
              className="mt-5 inline-flex h-12 w-full items-center justify-center rounded-full border border-border/35 bg-background/82 text-sm font-medium text-foreground/80 opacity-70"
              disabled
              type="button"
            >
              {texts.google}
            </button>

            <div className="my-5 flex items-center gap-3 text-xs text-foreground/42">
              <div className="h-px flex-1 bg-border/45" />
              <span>{texts.or}</span>
              <div className="h-px flex-1 bg-border/45" />
            </div>

            <div className="inline-flex rounded-full border border-border/35 bg-background/62 p-1">
              <button
                className={`rounded-full px-4 py-1.5 text-sm transition ${
                  tab === "login"
                    ? "bg-accent/18 text-foreground"
                    : "text-foreground/65 hover:text-foreground"
                }`}
                onClick={() => setTab("login")}
                type="button"
              >
                {texts.loginTitle}
              </button>
              <button
                className={`rounded-full px-4 py-1.5 text-sm transition ${
                  tab === "register"
                    ? "bg-accent/18 text-foreground"
                    : "text-foreground/65 hover:text-foreground"
                }`}
                onClick={() => setTab("register")}
                type="button"
              >
                {texts.register}
              </button>
            </div>

            {tab === "login" ? (
              <form className="mt-4 space-y-3" onSubmit={submitLogin}>
                <input
                  autoComplete="email"
                  className="h-12 w-full rounded-2xl border border-border/45 bg-background/72 px-4 text-sm text-foreground outline-none transition focus:border-accent/45 focus:ring-2 focus:ring-accent/20"
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder={texts.email}
                  type="email"
                  value={email}
                />
                <input
                  autoComplete="current-password"
                  className="h-12 w-full rounded-2xl border border-border/45 bg-background/72 px-4 text-sm text-foreground outline-none transition focus:border-accent/45 focus:ring-2 focus:ring-accent/20"
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={texts.password}
                  type="password"
                  value={password}
                />
                {error ? <p className="text-sm text-rose-500">{error}</p> : null}
                <button
                  className="mt-1 inline-flex h-12 w-full items-center justify-center rounded-full border border-accent/30 bg-accent/16 text-sm font-medium text-foreground transition hover:border-accent/55 hover:bg-accent/22 disabled:opacity-60"
                  disabled={submitting}
                  type="submit"
                >
                  {submitting ? (isZh ? "登录中..." : "Signing in...") : texts.login}
                </button>
              </form>
            ) : (
              <div className="mt-4 rounded-2xl border border-border/35 bg-background/56 p-4 text-sm text-foreground/75">
                {texts.disabledHint}
              </div>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <button
                className="inline-flex h-11 items-center justify-center rounded-2xl border border-border/35 bg-background/56 text-sm text-foreground/70"
                disabled
                type="button"
              >
                {texts.register}
              </button>
              <button
                className="inline-flex h-11 items-center justify-center rounded-2xl border border-border/35 bg-background/56 text-sm text-foreground/70"
                disabled
                type="button"
              >
                {texts.forgot}
              </button>
            </div>

            <p className="mt-4 text-center text-xs text-foreground/50">{texts.agree}</p>
          </section>
        </div>
      ) : null}
    </AuthModalContext.Provider>
  );
}
