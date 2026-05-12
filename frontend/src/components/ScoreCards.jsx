import React from "react";
import { motion } from "framer-motion";

export const ScoreGauge = ({ score, breakdown }) => {
  const pct = Math.max(0, Math.min(100, score));
  const dash = (pct / 100) * 283;
  const color = pct >= 70 ? "#F59E0B" : pct >= 45 ? "#09090B" : "#EF4444";

  return (
    <div className="border border-zinc-200 bg-white p-6" data-testid="opportunity-score-card">
      <div className="flex items-center justify-between mb-6">
        <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Opportunity Score</span>
        <span className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-400">0—100</span>
      </div>
      <div className="flex items-center gap-8">
        <div className="relative w-40 h-40 shrink-0">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="45" fill="none" stroke="#F3F4F6" strokeWidth="6" />
            <motion.circle
              cx="50" cy="50" r="45" fill="none" stroke={color} strokeWidth="6"
              strokeDasharray="283"
              initial={{ strokeDashoffset: 283 }}
              animate={{ strokeDashoffset: 283 - dash }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-4xl font-black tracking-tighter font-mono" data-testid="opportunity-score-value">{pct.toFixed(0)}</div>
            <div className="text-[9px] uppercase tracking-[0.2em] text-zinc-400 font-mono mt-1">SCORE</div>
          </div>
        </div>
        <div className="flex-1 space-y-3">
          {[
            { l: "Demand", v: breakdown?.demand || 0, max: 40 },
            { l: "Competition", v: breakdown?.competition || 0, max: 40 },
            { l: "Saturation Gap", v: breakdown?.saturation_gap || 0, max: 20 },
          ].map((b) => (
            <div key={b.l}>
              <div className="flex justify-between text-[10px] uppercase tracking-[0.2em] font-mono mb-1">
                <span className="text-zinc-600">{b.l}</span>
                <span>{b.v.toFixed(1)} / {b.max}</span>
              </div>
              <div className="h-1.5 bg-zinc-100">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(b.v / b.max) * 100}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                  className="h-full bg-black"
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const RatioMeter = ({ ratio, isGold }) => (
  <div
    data-testid="ratio-meter"
    className={`border p-6 transition-colors ${isGold ? "border-amber-500 bg-amber-50" : "border-zinc-200 bg-white"}`}
  >
    <div className="flex items-center justify-between mb-4">
      <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Competition / Order Ratio</span>
      {isGold && (
        <span className="text-[10px] uppercase tracking-[0.2em] font-mono bg-amber-500 text-white px-2 py-0.5">GOLD</span>
      )}
    </div>
    <div className="flex items-end gap-3">
      <div className={`text-6xl font-black tracking-tighter font-mono ${isGold ? "text-amber-600" : "text-black"}`} data-testid="ratio-value">
        {ratio?.toFixed(2) ?? "—"}
      </div>
      <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500 mb-2">
        avg orders / (total/100)
      </div>
    </div>
    <p className="text-xs font-mono text-zinc-500 mt-4 leading-relaxed">
      {isGold
        ? "ABOVE 5 — Algorithm signal: demand outpacing supply. Strong entry window."
        : "Below 5 — Niche operates within typical density. Consider long-tail pivots."}
    </p>
  </div>
);

export const MetricTile = ({ label, value, sublabel, testid, tone }) => {
  const toneCls = tone === "gold" ? "border-amber-500 bg-amber-50"
    : tone === "danger" ? "border-red-300 bg-red-50"
    : "border-zinc-200 bg-white";
  return (
    <div className={`border ${toneCls} p-4`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500">{label}</div>
      <div className={`text-2xl font-black tracking-tight mt-2 font-mono ${tone === "gold" ? "text-amber-600" : ""}`}>{value}</div>
      {sublabel && <div className="text-[10px] font-mono text-zinc-400 mt-1">{sublabel}</div>}
    </div>
  );
};

export const VelocityCard = ({ score, momentumGap, highTicketVacuum }) => {
  const pct = Math.max(0, Math.min(100, score || 0));
  return (
    <div className="border border-zinc-200 bg-white p-6" data-testid="velocity-card">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Velocity Score</span>
        <span className="text-[10px] font-mono text-zinc-400">2026 algorithm signal</span>
      </div>
      <div className="flex items-end gap-3 mb-3">
        <div className="text-6xl font-black tracking-tighter font-mono">{pct.toFixed(0)}</div>
        <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500 mb-2">
          orders · review-7d
        </div>
      </div>
      <div className="h-1.5 bg-zinc-100">
        <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8 }} className="h-full bg-amber-500" />
      </div>
      <div className="flex flex-wrap gap-2 mt-4">
        {momentumGap && (
          <span data-testid="badge-momentum-gap"
            className="text-[10px] uppercase tracking-[0.2em] font-mono bg-amber-500 text-white px-2 py-0.5">
            MOMENTUM GAP
          </span>
        )}
        {highTicketVacuum && (
          <span data-testid="badge-high-ticket-vacuum"
            className="text-[10px] uppercase tracking-[0.2em] font-mono bg-black text-amber-400 px-2 py-0.5">
            HIGH-TICKET VACUUM
          </span>
        )}
      </div>
    </div>
  );
};
