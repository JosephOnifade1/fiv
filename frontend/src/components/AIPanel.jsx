import React, { useState } from "react";
import { Sparkle, Robot, ArrowsHorizontal, ArrowRight } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

export const AIPanel = ({ job, authAxios, onPickKeyword }) => {
  const [summary, setSummary] = useState(null);
  const [pivots, setPivots] = useState(null);
  const [expansions, setExpansions] = useState(null);
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
      }
    } catch (e) {
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
          <div className="text-sm font-bold" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>Gemini 3 Flash</div>
        </div>
      </div>

      <div className="p-5 space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Button data-testid="ai-summary-btn" onClick={() => run("summary")} disabled={loading === "summary"}
            className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-xs uppercase tracking-[0.15em] h-10">
            <Sparkle size={12} weight="bold" className="mr-2" /> {loading === "summary" ? "Analyzing..." : "Summarize"}
          </Button>
          <Button data-testid="ai-pivots-btn" onClick={() => run("pivots")} disabled={loading === "pivots"}
            className="rounded-none bg-white hover:bg-zinc-100 text-black border border-zinc-300 font-mono text-xs uppercase tracking-[0.15em] h-10">
            <ArrowsHorizontal size={12} weight="bold" className="mr-2" /> {loading === "pivots" ? "Pivoting..." : "Side-step pivots"}
          </Button>
          <Button data-testid="ai-expand-btn" onClick={() => run("expand")} disabled={loading === "expand"}
            className="rounded-none bg-black hover:bg-zinc-800 text-white font-mono text-xs uppercase tracking-[0.15em] h-10">
            <ArrowRight size={12} weight="bold" className="mr-2" /> {loading === "expand" ? "Expanding..." : "Long-tail expand"}
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
      </div>
    </div>
  );
};
