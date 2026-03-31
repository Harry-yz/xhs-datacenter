import Link from "next/link";

import { type Locale } from "@/config/i18n";
import { cn } from "@/utils/cn";

export function LanguageSwitcher({ locale, pathname }: { locale: Locale; pathname: string }) {
  const zhPath = pathname.replace(`/${locale}`, "/zh");
  const enPath = pathname.replace(`/${locale}`, "/en");

  return (
    <div className="inline-flex items-center rounded-full border border-border/35 bg-background/72 p-1 backdrop-blur-xl">
      <Link
        className={cn(
          "inline-flex h-8 min-w-11 items-center justify-center rounded-full px-3 text-xs font-medium transition duration-300",
          locale === "zh" ? "bg-foreground text-background" : "text-foreground/58 hover:text-foreground"
        )}
        href={zhPath}
        prefetch={false}
      >
        中
      </Link>
      <Link
        className={cn(
          "inline-flex h-8 min-w-11 items-center justify-center rounded-full px-3 text-xs font-medium transition duration-300",
          locale === "en" ? "bg-foreground text-background" : "text-foreground/58 hover:text-foreground"
        )}
        href={enPath}
        prefetch={false}
      >
        EN
      </Link>
    </div>
  );
}
