"use client";

import { useSearchParams } from "next/navigation";

export function AuthButton({ label, fallbackNext }: { label: string; fallbackNext: string }) {
  const params = useSearchParams();
  const next = params.get("next") ?? fallbackNext;

  return (
    <form action="/api/mock-login" method="post">
      <input name="next" type="hidden" value={next} />
      <button
        className="inline-flex h-12 items-center justify-center rounded-full border border-accent/25 bg-accent/12 px-6 text-sm font-light text-foreground transition duration-300 hover:border-accent/55 hover:bg-accent/18"
        type="submit"
      >
        {label}
      </button>
    </form>
  );
}
