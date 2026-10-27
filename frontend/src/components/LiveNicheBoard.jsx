import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { useInterval } from "../hooks/useInterval";
import { Pulse, Crown, ArrowsClockwise, Lightning, Hammer } from "@phosphor-icons/react";

const fmtAgo = (iso) => {
  if (!iso) return "—";
  try {
    const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    return `${Math.round(s / 3600)}h ago`;
  } catch { return "—"; }
};

export const LiveNicheBoard = ({ activeTaskId, onPick, onBuild }) => {
  const { authAxios } = useAuth();
  const [niches, setNiches] = useState([]);
  const [onlyGold, setOnlyGold] = useState(false);
  const [flashIds, setFlashIds] = useState(new Set());
  const [lastUpdate, setLastUpdate] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await authAxios.get(`/niches?limit=12${onlyGold ? "&only_gold=true" : ""}`);
      setNiches((prev) => {
        const prevMap = Object.fromEntries(prev.map((n) => [n.keyword, n]));
        const fresh = new Set();
        for (const n of r.data.items) {
          const old = prevMap[n.keyword];
          if (!old || old.last_scanned !== n.last_scanned || old.status !== n.status) {
            fresh.add(n.keyword);
          }
        }
        if (fresh.size > 0) {
          setFlashIds(fresh);
          setTimeout(() => setFlashIds(new Set()), 1400);
        }
        return r.data.items;
      });
      setLastUpdate(new Date().toISOString());
    } catch {/* noop */}
  }, [authAxios, onlyGold]);

  useEffect(() => { load(); }, [load]);

  // Live polling: 10s while a scan is active, idle otherwise.
  useInterval(load, activeTaskId ? 10000 : null);

  return (
    <div className="border border-zinc-200 bg-white" data-testid="live-niche-board">
      <div className="flex items-center justify-between gap-3 flex-wrap px-5 py-3 border-b border-zinc-200">
        <div className="flex items-center gap-2">
          <span className="relative inline-flex">
            <Pulse size={14} weight="bold" className={activeTaskId ? "text-amber-500" : "text-zinc-400"} />
            {activeTaskId && (
              <span className="absolute inset-0 animate-ping">
                <Pulse size={14} weight="bold" className="text-amber-500 opacity-50" />
              </span>
            )}
          </span>
          <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-600">Live Niche Board</span>
          {activeTaskId && (
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] bg-amber-500 text-white px-2 py-0.5">
              LIVE · 10s
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            data-testid="board-gold-toggle"
            onClick={() => setOnlyGold((v) => !v)}
            className={`text-[10px] uppercase tracking-[0.15em] font-mono px-2.5 py-1 border transition-colors ${
              onlyGold ? "bg-amber-500 text-white border-amber-500" : "bg-white text-zinc-600 border-zinc-300 hover:border-black"
            }`}
          >
            <Crown size={11} weight="fill" className="inline mr-1" /> Gold only
          </button>
          <button
            data-testid="board-refresh"
            onClick={load}
            title="Refresh"
            className="text-[10px] uppercase tracking-[0.15em] font-mono px-2.5 py-1 border bg-white text-zinc-600 border-zinc-300 hover:border-black"
          >
            <ArrowsClockwise size={11} weight="bold" className="inline mr-1" /> Refresh
          </button>
          <span className="text-[10px] font-mono text-zinc-400">{fmtAgo(lastUpdate)}</span>
        </div>
      </div>

      {niches.length === 0 ? (
        <div className="px-5 py-6 text-xs font-mono text-zinc-400">
          No live niches yet. Hit Scan to populate the board.
        </div>
      ) : (
        <div className="divide-y divide-zinc-100">
          {niches.map((n) => {
            const flash = flashIds.has(n.keyword);
            const scanning = n.status === "scanning";
            return (
              <div
                key={n.keyword}
                role="button"
                tabIndex={0}
                data-testid={`niche-row-${n.keyword}`}
                onClick={() => onPick(n.display_keyword || n.keyword)}
                className={`w-full text-left flex items-center gap-3 px-5 py-3 transition-colors cursor-pointer ${
                  flash ? "bg-amber-50" : "hover:bg-zinc-50"
                } ${n.is_gold ? "border-l-2 border-amber-500" : "border-l-2 border-transparent"}`}
              >
                <div className="flex items-center gap-2 w-2 shrink-0">
                  {scanning ? (
                    <Lightning size={12} weight="fill" className="text-amber-500 animate-pulse" />
                  ) : n.is_gold ? (
                    <Crown size={12} weight="fill" className="text-amber-500" />
                  ) : (
                    <span className="w-1 h-1 rounded-full bg-zinc-300" />
                  )}
                </div>
                <span className="text-sm font-mono font-bold flex-1 truncate">{n.display_keyword || n.keyword}</span>
                <div className="flex items-center gap-4 text-[10px] font-mono">
                  {scanning ? (
                    <span className="text-amber-600 uppercase tracking-[0.2em]">scanning…</span>
                  ) : (
                    <>
                      <span className="text-zinc-500">{(n.total_gigs ?? 0).toLocaleString()} gigs</span>
                      <span className="text-zinc-500">{(n.avg_orders_in_queue ?? 0).toFixed(1)} q</span>
                      {n.is_gold && (
                        <span className="bg-amber-500 text-white px-1.5 py-0.5 uppercase tracking-[0.2em]">Gold</span>
                      )}
                      <span className="text-base font-black tracking-tight text-black min-w-[3rem] text-right">
                        {(n.score ?? 0).toFixed(0)}
                      </span>
                      <button
                        data-testid={`niche-build-gig-${n.keyword}`}
                        onClick={(e) => { e.stopPropagation(); onBuild(n.display_keyword || n.keyword); }}
                        title="Build a full gig setup for this niche"
                        className="flex items-center gap-1 border border-black px-2 py-1 uppercase tracking-[0.15em] hover:bg-amber-500 hover:border-amber-500 hover:text-white transition-colors"
                      >
                        <Hammer size={10} weight="bold" /> Build Gig
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
