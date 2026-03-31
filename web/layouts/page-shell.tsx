import { ReactNode } from "react";

export function PageShell({ children }: { children: ReactNode; dark?: boolean }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(247,171,214,0.22),transparent_18rem),radial-gradient(circle_at_top_right,rgba(255,204,132,0.24),transparent_20rem),radial-gradient(circle_at_bottom_right,rgba(150,220,244,0.18),transparent_24rem),linear-gradient(180deg,#fff8f3,#fffaf6_44%,#fffdf9)] dark:bg-[radial-gradient(circle_at_top_left,rgba(245,174,205,0.16),transparent_20rem),radial-gradient(circle_at_top_right,rgba(255,198,133,0.14),transparent_22rem),radial-gradient(circle_at_bottom_right,rgba(140,214,242,0.14),transparent_26rem),linear-gradient(180deg,#241f27,#29232c_38%,#2c2630)]">
      <div className="relative min-h-screen overflow-hidden">
        <div className="pointer-events-none absolute inset-0 opacity-[0.05] [background-image:linear-gradient(rgba(17,17,17,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(17,17,17,0.05)_1px,transparent_1px)] [background-size:48px_48px] dark:opacity-[0.1] dark:[background-image:linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.05)_1px,transparent_1px)]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-48 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.62),transparent_70%)] dark:bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.08),transparent_70%)]" />
        <div className="relative">{children}</div>
      </div>
    </div>
  );
}
