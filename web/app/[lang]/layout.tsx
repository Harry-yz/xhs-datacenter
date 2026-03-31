import { ReactNode } from "react";
import { notFound } from "next/navigation";
import { cookies } from "next/headers";

import { AuthModalProvider } from "@/components/providers/auth-modal-provider";
import { SESSION_COOKIE } from "@/config/i18n";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { isLocale, type Locale } from "@/config/i18n";
import { isAuthenticatedSession } from "@/config/auth";

export function generateStaticParams() {
  return [{ lang: "zh" }, { lang: "en" }];
}

export default function LocaleLayout({
  children,
  params
}: {
  children: ReactNode;
  params: { lang: string };
}) {
  if (!isLocale(params.lang)) {
    notFound();
  }

  const authenticated = isAuthenticatedSession(cookies().get(SESSION_COOKIE)?.value);

  return (
    <ThemeProvider>
      <AuthModalProvider initialAuthenticated={authenticated} locale={params.lang}>
        {children}
      </AuthModalProvider>
    </ThemeProvider>
  );
}

export type AppPageProps = {
  params: { lang: Locale };
  searchParams?: Record<string, string | string[] | undefined>;
};
