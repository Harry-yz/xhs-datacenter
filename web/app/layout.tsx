import type { Metadata } from "next";
import { cookies } from "next/headers";
import { ReactNode } from "react";

import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Oran Data Center",
  description: "Premium AI marketing data center for multi-platform content intelligence."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const locale = cookies().get("oran-locale")?.value ?? "zh";

  return (
    <html suppressHydrationWarning lang={locale}>
      <body>{children}</body>
    </html>
  );
}
