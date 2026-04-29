import { ReactNode } from "react";
import { notFound } from "next/navigation";

import { AuthModalProvider } from "@/components/providers/auth-modal-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { isLocale, type Locale } from "@/config/i18n";

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

  return (
    <ThemeProvider>
      <AuthModalProvider initialAuthenticated={false} locale={params.lang}>
        {children}
      </AuthModalProvider>
    </ThemeProvider>
  );
}

export type AppPageProps = {
  params: { lang: Locale };
  searchParams?: Record<string, string | string[] | undefined>;
};
