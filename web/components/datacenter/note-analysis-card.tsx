import Link from "next/link";

import { type NoteAnalysisCardVM } from "@/types/datacenter";

export function NoteAnalysisCard({
  item,
  href,
  likeLabel,
  saveLabel,
  commentLabel
}: {
  item: NoteAnalysisCardVM;
  href: string;
  likeLabel: string;
  saveLabel: string;
  commentLabel: string;
}) {
  return (
    <Link
      className="section-frame flex h-full flex-col gap-5 overflow-hidden transition duration-300 hover:-translate-y-1 hover:border-border/60 hover:shadow-card-hover"
      href={href}
    >
      <div className={`relative h-44 rounded-[1.7rem] bg-gradient-to-br ${item.coverColor}`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.35),transparent_28%)]" />
        <div className="absolute bottom-3 left-3 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/20 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-[#1d1f26]/72 backdrop-blur-md">
          <span>{item.author}</span>
          <span>·</span>
          <span>{item.followers}</span>
        </div>
      </div>
      <div className="space-y-3">
        <h3 className="text-xl leading-tight text-foreground">{item.title}</h3>
        <div className="grid grid-cols-3 gap-3 rounded-[1.25rem] border border-border/20 bg-foreground/5 p-3 text-sm text-foreground/72">
          <div>
            <div className="font-display text-lg text-foreground">{item.likeCount}</div>
            <div>{likeLabel}</div>
          </div>
          <div>
            <div className="font-display text-lg text-foreground">{item.collectionCount}</div>
            <div>{saveLabel}</div>
          </div>
          <div>
            <div className="font-display text-lg text-foreground">{item.commentCount}</div>
            <div>{commentLabel}</div>
          </div>
        </div>
      </div>

      <div className="space-y-3 pt-2">
        <div className="flex flex-wrap gap-2">
          {item.tags.map((tag) => (
            <span key={tag} className="rounded-full border border-border/35 bg-foreground/5 px-3 py-1 text-xs text-foreground/58">
              {tag}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {item.aiLabels.map((label) => (
            <span key={label} className="rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-xs text-accent">
              {label}
            </span>
          ))}
        </div>
      </div>
    </Link>
  );
}
