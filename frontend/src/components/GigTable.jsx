import React from "react";

const LevelBadge = ({ level, isPro }) => {
  const color = isPro ? "bg-black text-white"
    : level === "Top Rated" ? "bg-amber-500 text-white"
    : level === "Level 2" ? "bg-zinc-700 text-white"
    : level === "Level 1" ? "bg-zinc-200 text-zinc-700"
    : "bg-amber-50 text-amber-700 border border-amber-200";
  return (
    <span className={`text-[9px] uppercase tracking-[0.15em] font-mono px-1.5 py-0.5 ${color}`}>
      {isPro ? "PRO" : level}
    </span>
  );
};

const fmtDate = (s) => {
  try {
    const d = new Date(s);
    const h = Math.round((Date.now() - d.getTime()) / 3600000);
    if (h < 1) return "now";
    if (h < 24) return `${h}h ago`;
    return `${Math.round(h / 24)}d ago`;
  } catch {
    return "—";
  }
};

export const GigTable = ({ title, gigs, testid }) => (
  <div className="border border-zinc-200 bg-white" data-testid={testid}>
    <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200">
      <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-600">{title}</span>
      <span className="text-[10px] font-mono text-zinc-400">{gigs.length} gigs</span>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead className="bg-zinc-50 text-zinc-500">
          <tr>
            <th className="text-left px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">#</th>
            <th className="text-left px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Title</th>
            <th className="text-left px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Seller</th>
            <th className="text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Price</th>
            <th className="text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Queue</th>
            <th className="text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Rating</th>
            <th className="text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Last Rev</th>
          </tr>
        </thead>
        <tbody>
          {gigs.map((g, i) => (
            <tr key={i} className="border-t border-zinc-100 odd:bg-zinc-50/50 hover:bg-amber-50/40 transition-colors">
              <td className="px-3 py-2 text-zinc-400">{g.position}</td>
              <td className="px-3 py-2 max-w-[280px] truncate">{g.title}</td>
              <td className="px-3 py-2"><LevelBadge level={g.seller_level} isPro={g.is_fiverr_pro} /></td>
              <td className="px-3 py-2 text-right">${g.price_from}</td>
              <td className={`px-3 py-2 text-right font-bold ${g.orders_in_queue > 10 ? "text-amber-600" : ""}`}>
                {g.orders_in_queue}
              </td>
              <td className="px-3 py-2 text-right">{g.rating?.toFixed?.(1) ?? "—"}</td>
              <td className="px-3 py-2 text-right text-zinc-500">{fmtDate(g.last_review_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);
