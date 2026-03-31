import Link from "next/link";
import { ArrowLeft, Search } from "lucide-react";

export function PageToolbar({
  backHref,
  backLabel,
  searchAction,
  searchPlaceholder,
  searchValue,
  searchButtonLabel,
  compact = false
}: {
  backHref: string;
  backLabel: string;
  searchAction?: string;
  searchPlaceholder?: string;
  searchValue?: string;
  searchButtonLabel?: string;
  compact?: boolean;
}) {
  return (
    <div className={`flex flex-col gap-3 md:flex-row md:items-center md:justify-between ${compact ? "md:gap-2.5" : ""}`}>
      <Link
        className={`inline-flex w-fit items-center gap-2 rounded-full border border-border/35 bg-background/72 text-foreground/72 transition duration-300 hover:border-border/60 hover:text-foreground ${
          compact ? "px-3.5 py-1.5 text-xs" : "px-4 py-2 text-sm"
        }`}
        href={backHref}
      >
        <ArrowLeft className={compact ? "h-3.5 w-3.5" : "h-4 w-4"} />
        <span>{backLabel}</span>
      </Link>

      {searchAction ? (
        <form
          action={searchAction}
          className={`flex w-full max-w-xl items-center gap-2 rounded-full border border-border/35 bg-background/72 backdrop-blur-xl ${
            compact ? "p-1.5" : "p-2"
          }`}
          method="get"
        >
          <div
            className={`flex items-center justify-center rounded-full bg-foreground/5 text-foreground/55 ${
              compact ? "h-8 w-8" : "h-10 w-10"
            }`}
          >
            <Search className={compact ? "h-3.5 w-3.5" : "h-4 w-4"} />
          </div>
          <input
            className={`flex-1 bg-transparent px-1 text-foreground outline-none placeholder:text-foreground/38 ${
              compact ? "h-8 text-xs" : "h-10 text-sm"
            }`}
            defaultValue={searchValue}
            name="q"
            placeholder={searchPlaceholder}
            type="text"
          />
          <button
            className={`inline-flex items-center justify-center rounded-full bg-foreground text-background transition duration-300 hover:opacity-90 ${
              compact ? "h-8 px-3 text-xs" : "h-10 px-4 text-sm"
            }`}
            type="submit"
          >
            {searchButtonLabel}
          </button>
        </form>
      ) : null}
    </div>
  );
}
