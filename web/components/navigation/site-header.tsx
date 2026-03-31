"use client";

import Link from "next/link";

import { type Dictionary } from "@/config/dictionaries";
import { type Locale } from "@/config/i18n";
import { LanguageSwitcher } from "@/components/chrome/language-switcher";
import { ThemeToggle } from "@/components/chrome/theme-toggle";
import { useAuthModal } from "@/components/providers/auth-modal-provider";
import { withLocale } from "@/utils/routes";

export function SiteHeader({
  dictionary,
  locale,
  pathname,
  authenticated = false
}: {
  dictionary: Dictionary;
  locale: Locale;
  pathname: string;
  authenticated?: boolean;
}) {
  const auth = useAuthModal();
  const isAuthenticated = auth.authenticated || authenticated;

  return (
    <header className="sticky top-0 z-40 px-4 pt-4 md:px-8">
      <div className="mx-auto flex max-w-8xl items-center justify-between rounded-full border border-border/30 bg-background/62 px-5 py-3 backdrop-blur-sm">
        <Link className="font-display text-lg font-medium tracking-tight text-foreground" href={withLocale(locale, "/datacenter")}>
          {dictionary.brand}
        </Link>

        <div className="flex items-center gap-2">
          <LanguageSwitcher locale={locale} pathname={pathname} />
          <ThemeToggle />
          {isAuthenticated ? (
            <button
              className="inline-flex h-10 items-center justify-center rounded-full border border-border/40 bg-background/60 px-4 text-sm font-light text-foreground/72 transition duration-300 hover:border-border/70 hover:text-foreground"
              onClick={() => void auth.logout()}
              type="button"
            >
              {dictionary.navigation.logout}
            </button>
          ) : (
            <button
              className="inline-flex h-10 items-center justify-center rounded-full border border-accent/20 bg-accent/10 px-4 text-sm font-light text-foreground transition duration-300 hover:border-accent/45 hover:bg-accent/15"
              onClick={() => auth.openAuthModal({ next: pathname })}
              type="button"
            >
              {dictionary.navigation.login}
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
