import React, { useState } from "react";
import { Truck, Heart, Star, Megaphone } from "@phosphor-icons/react";

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
  } catch { return "—"; }
};

const fmtNum = (n) => {
  if (n == null) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toString();
};

const SORT_OPTS = [
  { key: "orders_in_queue", label: "Orders", Icon: Truck },
  { key: "favourites", label: "Favourites", Icon: Heart },
  { key: "reviews_count", label: "Reviews", Icon: Star },
];

export const GigTable = ({ title, gigs, testid }) => {
  const [sortKey, setSortKey] = useState("position");
  const sorted = sortKey === "position"
    ? gigs
    : [...gigs].sort((a, b) => (b[sortKey] || 0) - (a[sortKey] || 0));

  return (
    <div className="border border-zinc-200 bg-white" data-testid={testid}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 gap-3 flex-wrap">
        <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-600">{title}</span>
        <div className="flex items-center gap-1" data-testid={`${testid}-filters`}>
          <span className="text-[9px] uppercase tracking-[0.2em] font-mono text-zinc-400 mr-1">Sort</span>
          {SORT_OPTS.map(({ key, label, Icon }) => {
            const active = sortKey === key;
            return (
              <button
                key={key}
                data-testid={`${testid}-sort-${label.toLowerCase()}`}
                onClick={() => setSortKey(active ? "position" : key)}
                title={`Sort by ${label}`}
                className={`flex items-center gap-1 text-[10px] uppercase tracking-[0.15em] font-mono px-2 py-1 border transition-colors ${
                  active ? "bg-black text-white border-black"
                    : "bg-white text-zinc-600 border-zinc-300 hover:border-black"
                }`}
              >
                <Icon size={11} weight="bold" /> {label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead className="bg-zinc-50 text-zinc-500">
            <tr>
              <th className="text-left px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">#</th>
              <th className="text-left px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Title</th>
              <th className="text-left px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Seller</th>
              <th className="text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Price</th>
              <th className={`text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em] ${sortKey === "orders_in_queue" ? "text-amber-600" : ""}`}>
                <Truck size={10} weight="bold" className="inline mr-0.5" /> Orders
              </th>
              <th className={`text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em] ${sortKey === "favourites" ? "text-amber-600" : ""}`}>
                <Heart size={10} weight="bold" className="inline mr-0.5" /> Faves
              </th>
              <th className={`text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em] ${sortKey === "reviews_count" ? "text-amber-600" : ""}`}>
                <Star size={10} weight="bold" className="inline mr-0.5" /> Reviews
              </th>
              <th className="text-right px-3 py-2 font-normal text-[10px] uppercase tracking-[0.15em]">Last Rev</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((g, i) => (
              <tr key={i} className={`border-t border-zinc-100 odd:bg-zinc-50/50 hover:bg-amber-50/40 transition-colors ${g.is_promoted ? "relative" : ""}`}>
                <td className="px-3 py-2 text-zinc-400">{g.position}</td>
                <td className="px-3 py-2 max-w-[240px] truncate">
                  <span className="inline-flex items-center gap-1.5">
                    {g.is_promoted && (
                      <span title="Promoted gig (ad)" className="bg-zinc-900 text-amber-400 text-[8px] uppercase tracking-[0.15em] px-1 py-0.5 inline-flex items-center gap-0.5">
                        <Megaphone size={8} weight="bold" /> AD
                      </span>
                    )}
                    <span className="truncate">{g.title}</span>
                  </span>
                </td>
                <td className="px-3 py-2"><LevelBadge level={g.seller_level} isPro={g.is_fiverr_pro} /></td>
                <td className={`px-3 py-2 text-right ${g.price_from >= 200 ? "font-bold text-amber-600" : ""}`}>${g.price_from}</td>
                <td className={`px-3 py-2 text-right font-bold ${g.orders_in_queue > 10 ? "text-amber-600" : ""}`}>
                  {g.orders_in_queue}
                </td>
                <td className="px-3 py-2 text-right">{fmtNum(g.favourites)}</td>
                <td className="px-3 py-2 text-right">{fmtNum(g.reviews_count)} <span className="text-zinc-400">·{g.rating?.toFixed?.(1) ?? "—"}</span></td>
                <td className="px-3 py-2 text-right text-zinc-500">{fmtDate(g.last_review_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
