import React from "react";
import { CheckCircle, XCircle, LockSimple, Spinner } from "@phosphor-icons/react";
import { CopyButton } from "./parts";

const TYPE_LABEL = { free_text: "Free text", multiple_choice: "Multiple choice", file_upload: "File upload" };

export const RequirementsBody = ({ items }) => (
  <div className="space-y-2">
    {items.map((r, i) => (
      <div key={i} data-testid={`gig-requirement-${i}`} className="border border-zinc-200 p-3 flex justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] bg-black text-white px-2 py-0.5">{TYPE_LABEL[r.type]}</span>
            {r.required && <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">Required</span>}
          </div>
          <div className="text-sm font-bold">{r.question}</div>
          {r.options?.length > 0 && <div className="font-mono text-[11px] text-zinc-500 mt-1">{r.options.join(" · ")}</div>}
        </div>
        <CopyButton text={r.question} testid={`gig-requirement-copy-${i}`} />
      </div>
    ))}
  </div>
);

export const GalleryBody = ({ items }) => (
  <div className="grid md:grid-cols-3 gap-3">
    {items.map((g, i) => (
      <div key={i} data-testid={`gig-gallery-${i}`} className="border border-zinc-200 p-3 space-y-2">
        <div className="aspect-[4/3] bg-zinc-900 text-amber-400 flex items-center justify-center font-mono text-[10px] uppercase tracking-[0.3em]">
          Image {i + 1}
        </div>
        <div className="flex items-start justify-between gap-2">
          <code className="font-mono text-[11px] break-all">{g.filename}</code>
          <CopyButton text={g.filename} testid={`gig-gallery-copy-${i}`} />
        </div>
        <p className="font-mono text-[11px] text-zinc-500">{g.note}</p>
      </div>
    ))}
  </div>
);

const ICON = {
  pass: <CheckCircle size={14} weight="fill" className="text-amber-500" />,
  fail: <XCircle size={14} weight="fill" className="text-red-500" />,
  locked: <LockSimple size={14} weight="bold" className="text-zinc-400" />,
  pending: <Spinner size={14} className="animate-spin text-zinc-400" />,
};

export const Checklist = ({ checklist, score }) => (
  <div className="border border-black bg-white" data-testid="gig-checklist">
    <div className="bg-black text-white px-4 py-3 flex items-baseline justify-between">
      <span className="font-mono text-[10px] uppercase tracking-[0.3em]">Ranking checklist</span>
      <span className="text-2xl font-black tracking-tighter" data-testid="gig-checklist-score"
        style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
        {score.passed}<span className="text-zinc-500 text-base">/{score.total}</span>
      </span>
    </div>
    <ul className="divide-y divide-zinc-100">
      {checklist.map((c) => (
        <li key={c.key} data-testid={`gig-check-${c.key}`} data-status={c.status}
          className="flex items-center gap-2 px-4 py-2 font-mono text-[11px]">
          {ICON[c.status]}
          <span className={c.status === "locked" ? "text-zinc-400" : "text-zinc-700"}>{c.label}</span>
        </li>
      ))}
    </ul>
  </div>
);
