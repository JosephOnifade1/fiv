import React from "react";
import { ArrowRight, Spinner, WarningOctagon } from "@phosphor-icons/react";

const HEAD = { fontFamily: "'Cabinet Grotesk', system-ui" };
const SEV = { high: "bg-red-600 text-white", medium: "bg-amber-500 text-white", low: "bg-zinc-200 text-zinc-700" };
const pct = (s) => (s.total ? Math.round((s.passed / s.total) * 100) : 0);

const ScoreBox = ({ label, score, testid, gold }) => (
  <div className={`p-5 ${gold ? "bg-black text-white" : "bg-white"}`} data-testid={testid}>
    <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${gold ? "text-amber-400" : "text-zinc-500"}`}>{label}</div>
    <div className="text-5xl font-black tracking-tighter mt-1" style={HEAD}>{pct(score)}<span className="text-xl">%</span></div>
    <div className={`font-mono text-[11px] ${gold ? "text-zinc-400" : "text-zinc-500"}`}>{score.passed}/{score.total} ranking rules met</div>
  </div>
);

export const AuditSummary = ({ audit, after, pending, sectionTitles }) => (
  <section className="mb-8 border border-black" data-testid="gig-audit-summary">
    <div className="grid md:grid-cols-[1fr_auto_1fr] items-center bg-zinc-100 gap-px">
      <ScoreBox label="Your gig now" score={audit.before} testid="audit-before-score" />
      <div className="hidden md:flex px-4 justify-center bg-zinc-100"><ArrowRight size={22} weight="bold" /></div>
      <ScoreBox label="Rewritten gig" score={after} testid="audit-after-score" gold />
    </div>
    {audit.original?.title && sectionTitles?.[0] && (
      <div className="border-t border-zinc-200 px-5 py-3 font-mono text-xs space-y-1" data-testid="audit-title-compare">
        <div className="text-zinc-400 line-through">I will {audit.original.title}</div>
        <div className="font-bold">I will {sectionTitles[0].text}</div>
      </div>
    )}
    <div className="border-t border-zinc-200 bg-white">
      <div className="px-5 pt-4 pb-2 font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-500 flex items-center gap-2">
        <WarningOctagon size={12} weight="bold" /> What's holding your gig back
      </div>
      {pending ? (
        <div className="px-5 pb-4 flex items-center gap-2 font-mono text-xs text-zinc-500" data-testid="audit-issues-pending">
          <Spinner size={14} className="animate-spin text-amber-500" /> Auditing against the niche…
        </div>
      ) : !audit.issues?.length ? (
        <p className="px-5 pb-4 font-mono text-xs text-zinc-500" data-testid="audit-issues-empty">No issues could be listed for this gig.</p>
      ) : (
        <ul className="divide-y divide-zinc-100" data-testid="audit-issues-list">
          {audit.issues.map((i, n) => (
            <li key={n} className="px-5 py-3 grid md:grid-cols-[110px_1fr] gap-2" data-testid={`audit-issue-${n}`}>
              <div className="flex md:flex-col gap-1 items-start">
                <span className={`font-mono text-[9px] uppercase tracking-[0.2em] px-1.5 py-0.5 ${SEV[i.severity]}`}>{i.severity}</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">{i.section}</span>
              </div>
              <div>
                <div className="text-sm font-bold">{i.problem}</div>
                <div className="font-mono text-xs text-zinc-600 mt-1">Fix: {i.fix}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  </section>
);
