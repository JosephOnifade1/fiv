import React, { useState } from "react";
import { Sparkle, Robot, ArrowsHorizontal, ArrowRight, Compass, Graph } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

export const AIPanel = ({ job, authAxios, onPickKeyword }) => {
  const [summary, setSummary] = useState(null);
  const [pivots, setPivots] = useState(null);
  const [expansions, setExpansions] = useState(null);
  const [verdict, setVerdict] = useState(null);
  const [proximity, setProximity] = useState(null);
  const [loading, setLoading] = useState(null);

  if (!job || !job.result) return null;

  const run = async (kind) => {
    setLoading(kind);
    try {
      if (kind === "summary") {
        const r = await authAxios.post("/ai/summarize", { job_id: job.id });
        setSummary(r.data);
      } else if (kind === "pivots") {
        const r = await authAxios.post("/ai/pivots", { job_id: job.id });
        setPivots(r.data);
      } else if (kind === "expand") {
        const titles = (job.result.gigs || []).map((g) => g.title).slice(0, 50);
        const r = await authAxios.post("/ai/expand", { keyword: job.keyword, gig_titles: titles });
        setExpansions(r.data);
      } else if (kind === "verdict") {
        const r = await authAxios.post("/ai/trend-verdict", { job_id: job.id });
        setVerdict(r.data);
      } else if (kind === "proximity") {
        const r = await authAxios.post("/ai/proximity", { job_id: job.id });
        setProximity(r.data);
      }
    } catch {
      toast.error("AI request failed. Check Emergent LLM key balance.");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="border border-zinc-200 bg-[#FAFAFA]" data-testid="ai-panel">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-200 bg-white">
        <div className="w-8 h-8 bg-black flex items-center justify-center">
          <Robot size={16} weight="bold" color="#F59E0B" />
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">AI Niche Arbitrage Specialist</div>
          <div className="text-sm font-bold" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>Gemini 3 Flash · 2026 reverse-engineering mode</div>
        </div>
      </div>

      <div className="p-5 space-y-5">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
          <Button data-testid="ai-summary-btn" onClick={() => run("summary")} disabled={loading === "summary"}
            className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-[10px] uppercase tracking-[0.15em] h-10">
            <Sparkle size={11} weight="bold" className="mr-1" /> {loading === "summary" ? "..." : "Summarize"}
          </Button>
          <Button data-testid="ai-pivots-btn" onClick={() => run("pivots")} disabled={loading === "pivots"}
            className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-[10px] uppercase tracking-[0.15em] h-10">
            <ArrowsHorizontal size={11} weight="bold" className="mr-1" /> {loading === "pivots" ? "..." : "Side-step"}
          </Button>
          <Button data-testid="ai-expand-btn" onClick={() => run("expand")} disabled={loading === "expand"}
            className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-[10px] uppercase tracking-[0.15em] h-10">
            <ArrowRight size={11} weight="bold" className="mr-1" /> {loading === "expand" ? "..." : "Long-tail"}
          </Button>
          <Button data-testid="ai-verdict-btn" onClick={() => run("verdict")} disabled={loading === "verdict"}
            className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-[10px] uppercase tracking-[0.15em] h-10">
            <Compass size={11} weight="bold" className="mr-1" /> {loading === "verdict" ? "..." : "2026 Trend"}
          </Button>
          <Button data-testid="ai-proximity-btn" onClick={() => run("proximity")} disabled={loading === "proximity"}
            className="rounded-none bg-black hover:bg-zinc-800 text-white font-mono text-[10px] uppercase tracking-[0.15em] h-10">
            <Graph size={11} weight="bold" className="mr-1" /> {loading === "proximity" ? "..." : "Proximity"}
          </Button>
        </div>

        {summary && (
          <div data-testid="ai-summary-output" className="border border-zinc-200 bg-white p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Executive briefing</span>
              <span className={`text-[10px] uppercase tracking-[0.2em] font-mono px-2 py-0.5 ${
                summary.verdict === "GO" ? "bg-amber-500 text-white"
                : summary.verdict === "AVOID" ? "bg-red-500 text-white"
                : "bg-zinc-200 text-zinc-700"
              }`}>{summary.verdict}</span>
            </div>
            <ul className="space-y-2 text-sm font-mono text-zinc-700">
              {summary.bullets?.map((b, i) => (
                <li key={i} className="flex gap-3"><span className="text-amber-500 font-bold">▸</span>{b}</li>
              ))}
            </ul>
          </div>
        )}

        {verdict && (
          <div data-testid="ai-verdict-output" className={`border p-4 ${
            verdict.verdict === "LONG_TERM_SURGE" ? "border-amber-500 bg-amber-50"
            : verdict.verdict === "FLASH_IN_PAN" ? "border-red-300 bg-red-50"
            : "border-zinc-200 bg-white"
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">2026 Trend Verdict</span>
              <span className={`text-[10px] uppercase tracking-[0.2em] font-mono px-2 py-0.5 ${
                verdict.verdict === "LONG_TERM_SURGE" ? "bg-amber-500 text-white"
                : verdict.verdict === "FLASH_IN_PAN" ? "bg-red-500 text-white"
                : "bg-zinc-200 text-zinc-700"
              }`}>{verdict.verdict?.replace("_", " ")}</span>
            </div>
            <div className="flex flex-wrap gap-3 text-[11px] font-mono mb-2">
              {verdict.matched_trend && (
                <span className="bg-black text-amber-400 px-2 py-0.5 uppercase tracking-[0.15em]">{verdict.matched_trend}</span>
              )}
              {verdict.horizon_months != null && (
                <span className="text-zinc-500">Horizon: {verdict.horizon_months} mo</span>
              )}
            </div>
            <p className="text-xs font-mono text-zinc-600 leading-relaxed">{verdict.reasoning}</p>
          </div>
        )}

        {pivots?.pivots?.length > 0 && (
          <div data-testid="ai-pivots-output" className="space-y-2">
            <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 block mb-2">Side-step pivots</span>
            {pivots.pivots.map((p, i) => (
              <div key={i} className="border border-zinc-200 bg-white p-3">
                <div className="flex items-center justify-between gap-3">
                  <button onClick={() => onPickKeyword(p.pivot)}
                    className="text-sm font-bold text-left hover:text-amber-600 font-mono">{p.pivot}</button>
                  <span className="text-[10px] font-mono uppercase tracking-[0.15em] bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 shrink-0">
                    {p.estimated_demand_supply_ratio}
                  </span>
                </div>
                <p className="text-xs font-mono text-zinc-500 mt-2 leading-relaxed">{p.why}</p>
              </div>
            ))}
          </div>
        )}

        {expansions?.expansions?.length > 0 && (
          <div data-testid="ai-expansions-output" className="space-y-2">
            <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 block mb-2">Long-tail expansions</span>
            <div className="flex flex-wrap gap-2">
              {expansions.expansions.map((e, i) => (
                <button key={i} onClick={() => onPickKeyword(e.keyword)}
                  title={e.rationale}
                  className="text-xs font-mono border border-zinc-300 bg-white hover:bg-black hover:text-white px-3 py-1.5 transition-colors">
                  {e.keyword}
                </button>
              ))}
            </div>
          </div>
        )}

        {proximity && (
          <div data-testid="ai-proximity-output" className="space-y-3">
            <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 block">Keyword Proximity Map</span>
            <div className="border border-zinc-200 bg-white p-3">
              <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-400 mb-2">
                Live autocomplete neighbors ({proximity.autocomplete?.source})
              </div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {(proximity.autocomplete?.suggestions || []).map((s, i) => (
                  <button key={i} onClick={() => onPickKeyword(s)}
                    className="text-[11px] font-mono border border-zinc-300 px-2 py-1 hover:bg-black hover:text-white transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            </div>
            {proximity.map?.sidesteps?.length > 0 && (
              <div className="space-y-2">
                <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-400">Strongest side-steps</div>
                {proximity.map.sidesteps.map((s, i) => (
                  <div key={i} className="border border-zinc-200 bg-white p-3">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <button onClick={() => onPickKeyword(s.keyword)}
                        className="text-sm font-bold text-left hover:text-amber-600 font-mono">{s.keyword}</button>
                      <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.15em]">
                        <span className={`px-2 py-0.5 ${s.competition_estimate === "LOW" ? "bg-amber-50 text-amber-700 border border-amber-200" : "bg-zinc-100 text-zinc-600"}`}>
                          Comp: {s.competition_estimate}
                        </span>
                        <span className={`px-2 py-0.5 ${s.demand_estimate === "HIGH" ? "bg-black text-amber-400" : "bg-zinc-100 text-zinc-600"}`}>
                          Demand: {s.demand_estimate}
                        </span>
                        <span className="text-zinc-500">{s.audience_overlap_pct}% overlap</span>
                      </div>
                    </div>
                    <p className="text-xs font-mono text-zinc-500 mt-2 leading-relaxed">{s.rationale}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
