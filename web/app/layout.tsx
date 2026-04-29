import type { Metadata } from "next";
import { ReactNode } from "react";

import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Oran Data Center",
  description: "Premium AI marketing data center for multi-platform content intelligence."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html suppressHydrationWarning lang="zh">
      <body>{children}</body>
    </html>
  );
}
