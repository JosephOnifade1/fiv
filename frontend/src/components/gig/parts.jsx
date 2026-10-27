import React, { useState } from "react";
import { Copy, Check, ArrowsClockwise, LockSimple, Crown, Spinner } from "@phosphor-icons/react";
import { toast } from "sonner";

const HEAD = { fontFamily: "'Cabinet Grotesk', system-ui" };

export const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
};

export const CopyButton = ({ text, testid, label }) => {
  const [done, setDone] = useState(false);
  const onClick = async (e) => {
    e.stopPropagation();
    await copyText(text);
    setDone(true);
    toast.success("Copied");
    setTimeout(() => setDone(false), 1200);
  };
  return (
    <button data-testid={testid} onClick={onClick} title="Copy"
      className="shrink-0 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-[0.15em] px-2 py-1 border border-zinc-300 bg-white hover:bg-black hover:text-white transition-colors">
      {done ? <Check size={11} weight="bold" /> : <Copy size={11} weight="bold" />}
      {label}
    </button>
  );
};

export const Counter = ({ value, max, testid }) => (
  <span data-testid={testid}
    className={`font-mono text-[11px] tabular-nums ${value > max ? "text-red-600 font-bold" : "text-zinc-400"}`}>
    {value}/{max}
  </span>
);

const LockedBody = ({ onUpgrade, id }) => (
  <div className="relative" data-testid={`gig-locked-${id}`}>
    <div className="blur-sm select-none pointer-events-none space-y-2 p-1" aria-hidden>
      {[90, 70, 85, 60].map((w, i) => (
        <div key={i} className="h-4 bg-zinc-200" style={{ width: `${w}%` }} />
      ))}
      <p className="font-mono text-xs text-zinc-400">Premium keyword-rich copy written from live niche data.</p>
    </div>
    <div className="absolute inset-0 flex items-center justify-center">
      <button data-testid={`gig-upgrade-${id}`} onClick={onUpgrade}
        className="inline-flex items-center gap-2 bg-black text-white px-4 py-2 font-mono text-[11px] uppercase tracking-[0.2em] hover:bg-amber-500 transition-colors">
        <LockSimple size={12} weight="bold" /> Upgrade to Pro
      </button>
    </div>
  </div>
);

export const SectionShell = ({ id, step, title, locked, pending, failed, copyValue, onRegen, regenBusy, onUpgrade, children }) => (
  <section data-testid={`gig-section-${id}`} className="border border-zinc-200 bg-white">
    <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-zinc-200">
      <div className="flex items-center gap-3 min-w-0">
        {step && <span className="font-mono text-[10px] text-zinc-400 tracking-[0.2em]">{step}</span>}
        <h3 className="font-black tracking-tight text-base truncate" style={HEAD}>{title}</h3>
        {locked && <Crown size={12} weight="fill" className="text-amber-500" />}
      </div>
      {!locked && !pending && (
        <div className="flex items-center gap-2">
          {copyValue && <CopyButton text={copyValue} testid={`gig-copy-${id}`} label="Copy" />}
          <button data-testid={`gig-regen-${id}`} onClick={onRegen} disabled={regenBusy}
            className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-[0.15em] px-2 py-1 border border-black bg-black text-white hover:bg-amber-500 hover:border-amber-500 transition-colors disabled:opacity-50">
            <ArrowsClockwise size={11} weight="bold" className={regenBusy ? "animate-spin" : ""} />
            {regenBusy ? "Writing" : "Regenerate"}
          </button>
        </div>
      )}
    </div>
    <div className="p-5">
      {locked ? <LockedBody onUpgrade={onUpgrade} id={id} />
        : pending ? (
          <div className="flex items-center gap-2 font-mono text-xs text-zinc-500" data-testid={`gig-pending-${id}`}>
            <Spinner size={14} className="animate-spin text-amber-500" /> Writing from scan data…
          </div>
        ) : failed ? (
          <p className="font-mono text-xs text-red-600" data-testid={`gig-failed-${id}`}>
            This section could not be written. Hit Regenerate to try again.
          </p>
        ) : children}
    </div>
  </section>
);
