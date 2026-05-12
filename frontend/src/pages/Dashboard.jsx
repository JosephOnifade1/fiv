import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "../AuthContext";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  TrendUp, BookmarkSimple, SignOut, FileCsv, FileText,
  Clock, ChartLineUp, Tag, Circle, XCircle,
} from "@phosphor-icons/react";
import { ScoreGauge, RatioMeter, MetricTile, VelocityCard } from "../components/ScoreCards";
import { GigTable } from "../components/GigTable";
import { AIPanel } from "../components/AIPanel";
import { TopFocusKeywords } from "../components/TopFocusKeywords";
import { SearchBar } from "../components/SearchBar";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

export default function Dashboard() {
  const { user, logout, authAxios } = useAuth();
  const [keyword, setKeyword] = useState("");
  const [activeJob, setActiveJob] = useState(null);
  const [polling, setPolling] = useState(false);
  const [history, setHistory] = useState([]);
  const [watchlist, setWatchlist] = useState([]);
  const [trendData, setTrendData] = useState([]);

  const refreshHistory = useCallback(async () => {
    const r = await authAxios.get("/scrape/jobs");
    setHistory(r.data);
  }, [authAxios]);

  const refreshWatchlist = useCallback(async () => {
    const r = await authAxios.get("/watchlist");
    setWatchlist(r.data);
  }, [authAxios]);

  const fetchTrends = useCallback(async (kw) => {
    try {
      const r = await authAxios.get(`/trends/${encodeURIComponent(kw)}`);
      setTrendData(r.data.snapshots.map((s) => ({
        date: new Date(s.captured_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
        services: s.total_services,
        orders: s.avg_orders_in_queue,
        score: s.opportunity_score,
      })));
    } catch {/* noop */}
  }, [authAxios]);

  useEffect(() => { refreshHistory(); refreshWatchlist(); }, [refreshHistory, refreshWatchlist]);

  const startSearch = async (kw) => {
    const term = (kw || keyword).trim();
    if (!term) return;
    setKeyword(term);
    setPolling(true);
    try {
      const r = await authAxios.post("/scrape/search", { keyword: term });
      const jobId = r.data.job_id;
      setActiveJob({ id: jobId, keyword: term, status: "running", result: null });
      pollJob(jobId);
    } catch {
      toast.error("Failed to start scrape");
      setPolling(false);
    }
  };

  const pollJob = async (jobId) => {
    for (let i = 0; i < 30; i++) {
      await new Promise((res) => setTimeout(res, 1500));
      try {
        const r = await authAxios.get(`/scrape/jobs/${jobId}`);
        if (r.data.status === "complete") {
          setActiveJob(r.data);
          setPolling(false);
          refreshHistory();
          fetchTrends(r.data.keyword);
          toast.success(`Scrape complete · Score ${r.data.result?.opportunity_score}`);
          return;
        }
        if (r.data.status === "failed") {
          setPolling(false);
          toast.error("Scrape failed");
          return;
        }
      } catch {/* noop */}
    }
    setPolling(false);
  };

  const loadJob = async (jobId) => {
    const r = await authAxios.get(`/scrape/jobs/${jobId}`);
    setActiveJob(r.data);
    setKeyword(r.data.keyword);
    fetchTrends(r.data.keyword);
  };

  const exportJob = async (fmt) => {
    if (!activeJob) return;
    const url = `${authAxios.defaults.baseURL}/scrape/jobs/${activeJob.id}/export?format=${fmt}`;
    const res = await fetch(url, { headers: authAxios.defaults.headers });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `fiverr_${activeJob.keyword}.${fmt}`;
    a.click();
  };

  const addWatch = async () => {
    if (!activeJob) return;
    await authAxios.post("/watchlist", { keyword: activeJob.keyword });
    toast.success("Added to watchlist");
    refreshWatchlist();
  };

  const removeWatch = async (id) => {
    await authAxios.delete(`/watchlist/${id}`);
    refreshWatchlist();
  };

  const result = activeJob?.result;
  const gigs = result?.gigs || [];
  const top10 = gigs.filter((g) => g.position <= 10);
  const bot10 = gigs.filter((g) => g.position > 10);

  return (
    <div className="min-h-screen bg-white">
      {/* Top bar */}
      <header className="border-b border-zinc-200 bg-white sticky top-0 z-20">
        <div className="flex items-center justify-between px-6 lg:px-8 h-14">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-black flex items-center justify-center">
              <TrendUp size={14} weight="bold" color="#F59E0B" />
            </div>
            <span className="font-black tracking-tight text-sm" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
              FIVERR&nbsp;SCOUT
            </span>
            <span className="text-[10px] uppercase tracking-[0.3em] text-zinc-400 font-mono hidden sm:inline">
              Niche Arbitrage Terminal
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-xs font-mono text-zinc-500 hidden sm:inline" data-testid="user-email">{user?.email}</span>
            <button onClick={logout} data-testid="logout-btn"
              className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-600 hover:text-black flex items-center gap-1">
              <SignOut size={14} weight="bold" /> Sign out
            </button>
          </div>
        </div>
      </header>

      <div className="grid lg:grid-cols-[260px_1fr] min-h-[calc(100vh-3.5rem)]">
        {/* Sidebar */}
        <aside className="border-r border-zinc-200 bg-zinc-50/50 p-4 lg:p-5 space-y-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono mb-3 flex items-center gap-2">
              <Clock size={12} weight="bold" /> History
            </div>
            <div className="space-y-1 max-h-64 overflow-y-auto" data-testid="history-list">
              {history.length === 0 && <p className="text-xs font-mono text-zinc-400">No searches yet.</p>}
              {history.map((j) => (
                <button key={j.id} onClick={() => loadJob(j.id)}
                  className="w-full text-left px-2 py-1.5 border border-transparent hover:border-zinc-300 hover:bg-white transition-colors group">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono truncate">{j.keyword}</span>
                    <span className="text-[9px] font-mono text-zinc-400">
                      {j.status === "complete" ? `${j.result?.opportunity_score?.toFixed?.(0) ?? "—"}` :
                       j.status === "running" ? "..." : "✕"}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono mb-3 flex items-center gap-2">
              <BookmarkSimple size={12} weight="bold" /> Watchlist
            </div>
            <div className="space-y-2" data-testid="watchlist">
              {watchlist.length === 0 && <p className="text-xs font-mono text-zinc-400">Empty.</p>}
              {watchlist.map((w) => (
                <div key={w.id} className="border border-zinc-200 bg-white p-2">
                  <div className="flex items-center justify-between gap-1">
                    <button onClick={() => startSearch(w.keyword)} className="text-xs font-mono font-bold text-left hover:text-amber-600 truncate flex-1">
                      {w.keyword}
                    </button>
                    <button onClick={() => removeWatch(w.id)} className="text-zinc-400 hover:text-red-500">
                      <XCircle size={14} weight="bold" />
                    </button>
                  </div>
                  {w.latest_snapshot && (
                    <div className="text-[10px] font-mono text-zinc-500 mt-1 flex justify-between">
                      <span>Score {w.latest_snapshot.opportunity_score?.toFixed?.(0)}</span>
                      {w.week_over_week_pct != null && (
                        <span className={w.week_over_week_pct > 10 ? "text-amber-600 font-bold" : ""}>
                          {w.week_over_week_pct > 0 ? "+" : ""}{w.week_over_week_pct}%
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="p-6 lg:p-8 space-y-6 max-w-[1600px]">
          {/* Search */}
          <SearchBar value={keyword} onChange={setKeyword} onSubmit={startSearch} busy={polling} authAxios={authAxios} />

          {!result && !polling && (
            <>
              <div className="border border-zinc-200 bg-zinc-50 p-12 text-center">
                <p className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-400 mb-3">Empty terminal</p>
                <h2 className="text-2xl font-black tracking-tight mb-2" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
                  Scan a keyword to begin.
                </h2>
                <p className="text-xs font-mono text-zinc-500 max-w-md mx-auto">
                  Try a long-tail phrase like <span className="font-bold">"logo for bio-hacking startups"</span> or
                  broader like <span className="font-bold">"video editing"</span>.
                </p>
              </div>
              <TopFocusKeywords authAxios={authAxios} onPick={startSearch} refreshKey={history.length} />
            </>
          )}

          {result && (
            <>
              {/* Banner */}
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Current scan</div>
                  <h1 className="text-3xl lg:text-4xl font-black tracking-tighter" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}
                      data-testid="active-keyword">
                    {activeJob.keyword}
                  </h1>
                  <div className="flex items-center gap-3 mt-1 text-[10px] font-mono uppercase tracking-[0.2em]">
                    <span className="flex items-center gap-1 text-zinc-500">
                      <Circle size={6} weight="fill" className={result.data_source === "live" ? "text-green-500" : "text-amber-500"} />
                      {result.data_source === "live" ? "LIVE SCRAPE" : "STEALTH FALLBACK"}
                    </span>
                    <span className="text-zinc-400">{new Date(result.scraped_at).toLocaleString()}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button onClick={addWatch} data-testid="add-watchlist-btn"
                    className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-xs uppercase tracking-[0.15em] h-9">
                    <BookmarkSimple size={12} weight="bold" className="mr-1" /> Watch
                  </Button>
                  <Button onClick={() => exportJob("csv")} data-testid="export-csv-btn"
                    className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-xs uppercase tracking-[0.15em] h-9">
                    <FileCsv size={12} weight="bold" className="mr-1" /> CSV
                  </Button>
                  <Button onClick={() => exportJob("json")} data-testid="export-json-btn"
                    className="rounded-none bg-black hover:bg-zinc-800 text-white font-mono text-xs uppercase tracking-[0.15em] h-9">
                    <FileText size={12} weight="bold" className="mr-1" /> JSON
                  </Button>
                </div>
              </div>

              {/* Score + Ratio + Velocity */}
              <div className="grid lg:grid-cols-3 gap-4">
                <ScoreGauge score={result.opportunity_score} breakdown={result.breakdown} />
                <RatioMeter ratio={result.competition_to_order_ratio} isGold={result.ratio_is_gold} />
                <VelocityCard score={result.velocity_score}
                  momentumGap={result.momentum_gap} highTicketVacuum={result.high_ticket_vacuum} />
              </div>

              {/* Metrics — 2026 reverse-engineering signals */}
              <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-px bg-zinc-200">
                <MetricTile testid="metric-total" label="Total Gigs" value={result.metrics.total_services.toLocaleString()} sublabel={result.metrics.total_services < 2000 ? "LOW COMP" : "DENSE"} />
                <MetricTile testid="metric-queue" label="Avg Queue" value={result.metrics.avg_orders_in_queue} sublabel={`top10 ${result.metrics.avg_queue_top10}`} />
                <MetricTile testid="metric-saturation-index" label="Saturation Index"
                  value={result.saturation_index}
                  sublabel={result.saturation_index > 50 ? "HUNGRY" : "FED"}
                  tone={result.saturation_index > 60 ? "gold" : undefined} />
                <MetricTile testid="metric-promoted" label="Promoted CPA"
                  value={`${result.promoted_cpa_pct}%`}
                  sublabel={result.promoted_cpa_signal?.replace("_", " ")}
                  tone={result.promoted_cpa_signal === "WIDE_OPEN" ? "gold" : (result.promoted_cpa_signal === "CROWDED" ? "danger" : undefined)} />
                <MetricTile testid="metric-velocity-meta" label="Velocity"
                  value={result.velocity_score}
                  sublabel={`${result.metrics.reviews_last_7d} rev/7d`}
                  tone={result.velocity_score > 50 ? "gold" : undefined} />
                <MetricTile testid="metric-median" label="Median Price" value={`$${result.metrics.median_price}`}
                  sublabel={result.metrics.price_inflation_pct != null ? `${result.metrics.price_inflation_pct >= 0 ? "+" : ""}${result.metrics.price_inflation_pct}% vs prior` : "no prior"}
                  tone={(result.metrics.price_inflation_pct || 0) > 20 ? "gold" : undefined} />
                <MetricTile testid="metric-ceiling" label="Top Decile" value={`$${result.metrics.top_decile_price}`}
                  sublabel={result.high_ticket_vacuum ? "HIGH-TICKET VACUUM" : `${result.metrics.high_ticket_count} ≥$200 +queue`}
                  tone={result.high_ticket_vacuum ? "gold" : undefined} />
              </div>

              {/* AI */}
              <AIPanel job={activeJob} authAxios={authAxios} onPickKeyword={startSearch} />

              {/* Top focus keywords across all scans */}
              <TopFocusKeywords authAxios={authAxios} onPick={startSearch} refreshKey={history.length} />

              {/* Tables */}
              <div className="grid lg:grid-cols-2 gap-4">
                <GigTable testid="top10-table" title="Top 10 — first page" gigs={top10} />
                <GigTable testid="bottom10-table" title="Bottom 10 — first page" gigs={bot10} />
              </div>

              {/* Trends */}
              {trendData.length > 1 && (
                <div className="border border-zinc-200 bg-white p-5" data-testid="trend-chart">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 flex items-center gap-2">
                      <ChartLineUp size={12} weight="bold" /> Trend (week-over-week)
                    </span>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={trendData}>
                      <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" />
                      <XAxis dataKey="date" stroke="#52525B" fontSize={10} fontFamily="IBM Plex Mono" />
                      <YAxis yAxisId="left" stroke="#52525B" fontSize={10} fontFamily="IBM Plex Mono" />
                      <YAxis yAxisId="right" orientation="right" stroke="#F59E0B" fontSize={10} fontFamily="IBM Plex Mono" />
                      <Tooltip contentStyle={{ fontFamily: "IBM Plex Mono", fontSize: 11, border: "1px solid #E5E7EB" }} />
                      <Line yAxisId="left" type="monotone" dataKey="services" stroke="#09090B" strokeWidth={1.5} dot={false} name="Total gigs" />
                      <Line yAxisId="right" type="monotone" dataKey="orders" stroke="#F59E0B" strokeWidth={1.5} dot={false} name="Avg queue" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Tags */}
              {result.tags?.length > 0 && (
                <div className="border border-zinc-200 bg-white p-5" data-testid="tag-cloud">
                  <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-3 flex items-center gap-2">
                    <Tag size={12} weight="bold" /> Cross-reference tags (top 3 gigs)
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {result.tags.map((t, i) => (
                      <button key={i} onClick={() => startSearch(t)}
                        className="text-xs font-mono border border-zinc-300 bg-white hover:bg-black hover:text-white px-3 py-1.5 transition-colors">
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
