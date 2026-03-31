import Link from "next/link";

import { type PlatformCardVM } from "@/types/datacenter";

export function PlatformCard({
  item,
  href,
  notesLabel,
  creatorsLabel
}: {
  item: PlatformCardVM;
  href?: string;
  notesLabel: string;
  creatorsLabel: string;
}) {
  const content = (
    <article className="relative h-full overflow-hidden rounded-[2rem] p-5 text-[#1d1f26] shadow-[0_18px_48px_rgba(12,18,30,0.14)] transition-all duration-500 ease-in-out will-change-transform group-hover:-translate-y-1 group-hover:shadow-[0_30px_76px_rgba(10,14,24,0.22)] dark:shadow-[0_20px_54px_rgba(0,0,0,0.38)] dark:group-hover:shadow-[0_36px_92px_rgba(0,0,0,0.52)]">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.88] transition-all duration-500 ease-in-out [filter:saturate(92%)_grayscale(14%)_blur(0.35px)] group-hover:opacity-[0.98] group-hover:[filter:saturate(100%)_grayscale(0%)_blur(0px)]"
        style={{ backgroundImage: item.gradient, borderRadius: "2rem" }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-72 transition-all duration-500 ease-in-out group-hover:opacity-80 dark:opacity-54 dark:group-hover:opacity-62"
        style={{
          backgroundImage: "radial-gradient(circle at top right, rgba(255,255,255,0.36), transparent 31%)",
          borderRadius: "2rem"
        }}
      />
      <div className="pointer-events-none absolute -right-10 top-8 h-40 w-40 rounded-full bg-white/12 blur-3xl transition-all duration-500 ease-in-out group-hover:bg-white/16 dark:bg-white/10 dark:group-hover:bg-white/12" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/8 to-transparent opacity-18 transition-all duration-500 ease-in-out group-hover:opacity-22 dark:from-black/18 dark:opacity-28" />

      <div className="relative flex h-full min-h-[248px] flex-col justify-between">
        <div className="flex items-start justify-between">
          <span className="rounded-full bg-white/34 px-3 py-1 text-[10px] font-light uppercase tracking-[0.18em] text-[#1d1f26]/75">
            Oran AI
          </span>
        </div>

        <div className="space-y-2.5">
          <div className="h-px w-12 bg-[#1d1f26]/20 transition duration-500 group-hover:w-[3.6rem]" />
          <h3 className="text-[clamp(1.38rem,2vw,1.9rem)] leading-[0.98] text-[#1d1f26]">{item.platform}</h3>
          <p className="max-w-[15rem] text-[11px] font-normal leading-5 text-[#1d1f26]/72 md:text-xs">{item.description}</p>
        </div>

        <div className="rounded-[1.5rem] border border-black/6 bg-white/16 p-3.5 backdrop-blur-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="tabular-nums text-[1.45rem] font-medium tracking-tight md:text-[1.6rem]">{item.notes}</div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-[#1d1f26]/55">{notesLabel}</div>
            </div>
            <div>
              <div className="tabular-nums text-[1.45rem] font-medium tracking-tight md:text-[1.6rem]">{item.creators}</div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-[#1d1f26]/55">{creatorsLabel}</div>
            </div>
          </div>
        </div>
      </div>
    </article>
  );

  const wrapperClassName = `group block h-full ${item.status === "available" && href ? "cursor-pointer" : "cursor-default"}`;

  return item.status === "available" && href ? (
    <Link className={wrapperClassName} href={href}>
      {content}
    </Link>
  ) : (
    <div className={wrapperClassName}>{content}</div>
  );
}
