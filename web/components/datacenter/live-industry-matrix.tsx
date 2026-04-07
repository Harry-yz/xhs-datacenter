"use client";

import { useEffect, useState } from "react";

import { IndustryCard } from "@/components/datacenter/industry-card";
import { useAuthModal } from "@/components/providers/auth-modal-provider";
import type { Locale } from "@/config/i18n";
import type { IndustryCardVM } from "@/types/datacenter";

type LiveIndustryItem = {
  industryKey: string;
  industryName: string;
  noteCount: number;
};

type LiveIndustryPayload = {
  items: LiveIndustryItem[];
  generatedAt: string;
};

function toLocaleCount(locale: Locale, value: number) {
  return Math.max(0, Math.round(value)).toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}

function toValueLabel(locale: Locale, count: number) {
  return `${toLocaleCount(locale, count)} ${locale === "zh" ? "笔记" : "Notes"}`;
}

function buildHref(searchBasePath: string, item: IndustryCardVM) {
  return `${searchBasePath}?${new URLSearchParams({
    type: "category",
    q: item.name,
    ...(item.industryKey ? { industry: item.industryKey } : {})
  }).toString()}`;
}

export function LiveIndustryMatrix({
  initialIndustries,
  locale,
  searchBasePath,
  authenticated,
}: {
  initialIndustries: IndustryCardVM[];
  locale: Locale;
  searchBasePath: string;
  authenticated: boolean;
}) {
  const auth = useAuthModal();
  const [industries, setIndustries] = useState<IndustryCardVM[]>(initialIndustries);

  useEffect(() => {
    setIndustries(initialIndustries);
  }, [initialIndustries]);

  useEffect(() => {
    async function refreshIndustries() {
      if (document.hidden) {
        return;
      }
      try {
        const response = await fetch("/api/dashboard/xhs/live-industries", {
          cache: "no-store"
        });
        if (!response.ok) {
          throw new Error("live industries api failed");
        }
        const payload = (await response.json()) as LiveIndustryPayload;
        const items = Array.isArray(payload.items) ? payload.items : [];
        if (!items.length) {
          return;
        }

        setIndustries((prev) => {
          const countsByKey = new Map(items.map((item) => [item.industryKey, item.noteCount]));
          return prev.map((item) => {
            if (!item.industryKey) {
              return item;
            }
            const nextCount = countsByKey.get(item.industryKey);
            if (nextCount === undefined) {
              return item;
            }
            return {
              ...item,
              value: toValueLabel(locale, nextCount)
            };
          });
        });
      } catch {
        // Keep previous values on transient failures.
      }
    }

    function onVisibilityChange() {
      if (!document.hidden) {
        void refreshIndustries();
      }
    }

    const timer = window.setInterval(() => {
      void refreshIndustries();
    }, 60000);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [locale]);

  return (
    <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
      {industries.map((item) => (
        <IndustryCard
          key={`${item.industryKey ?? item.name}-${item.name}`}
          href={buildHref(searchBasePath, item)}
          item={item}
          // Auth gate must remain for industry card navigation.
          onClick={(event) => {
            if (authenticated || auth.authenticated) {
              return;
            }
            event.preventDefault();
            auth.openAuthModal({ next: buildHref(searchBasePath, item) });
          }}
        />
      ))}
    </div>
  );
}
