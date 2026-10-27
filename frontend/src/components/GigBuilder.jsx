import React, { useCallback, useEffect, useState } from "react";
import { ArrowLeft, FileDoc, Warning, Spinner, Hammer } from "@phosphor-icons/react";
import { toast } from "sonner";
import { useAuth } from "../AuthContext";
import { useInterval } from "../hooks/useInterval";
import { SectionShell } from "./gig/parts";
import { TitlesBody, CategoryBody, TagsBody } from "./gig/OverviewSections";
import { PricingBody, DescriptionBody, FaqBody, pricingText } from "./gig/ContentSections";
import { RequirementsBody, GalleryBody, Checklist } from "./gig/ExtraSections";
import { AuditSummary } from "./gig/AuditSummary";

const HEAD = { fontFamily: "'Cabinet Grotesk', system-ui" };
const STEPS = [
  ["overview", "01", "Overview"], ["pricing", "02", "Pricing"], ["content", "03", "Description & FAQ"],
  ["requirements", "04", "Requirements"], ["gallery", "05", "Gallery"],
];

const copyFor = {
  titles: (v) => v.map((t) => `I will ${t.text}`).join("\n"),
  category: (v) => [v.category, v.subcategory, v.service_type].join(" > "),
  tags: (v) => v.join(", "),
  pricing: pricingText,
  description: (v) => v,
  faq: (v) => v.map((f) => `Q: ${f.question}\nA: ${f.answer}`).join("\n\n"),
  requirements: (v) => v.map((r, i) => `${i + 1}. ${r.question}`).join("\n"),
  gallery: (v) => v.map((g) => g.filename).join("\n"),
};

export const GigBuilder = ({ setupId, onClose, onUpgrade, onRescan }) => {
  const { authAxios } = useAuth();
  const [setup, setSetup] = useState(null);
  const [regen, setRegen] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await authAxios.get(`/gigs/${setupId}`);
      setSetup(r.data);
    } catch { toast.error("Could not load gig setup"); }
  }, [authAxios, setupId]);

  useEffect(() => { load(); }, [load]);
  useInterval(load, setup?.status === "building" ? 2000 : null);

  const regenerate = async (section) => {
    setRegen(section);
    try {
      const r = await authAxios.post(`/gigs/${setupId}/regenerate`, { section });
      setSetup(r.data);
      toast.success("Section rewritten");
    } catch (e) {
      if (e?.response?.status === 402) onUpgrade();
      else toast.error("Regenerate failed, try again");
    } finally { setRegen(null); }
  };

  const save = async (section, value) => {
    try {
      const r = await authAxios.patch(`/gigs/${setupId}`, { section, value });
      setSetup(r.data);
      toast.success("Saved");
    } catch { toast.error("Save failed"); }
  };

  const download = async () => {
    if (!setup.is_pro) return onUpgrade();
    const res = await fetch(`${authAxios.defaults.baseURL}/gigs/${setupId}/docx`, { headers: authAxios.defaults.headers });
    if (!res.ok) return toast.error("Download failed");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `gig_setup_${setup.keyword.replace(/\s+/g, "_")}.docx`;
    a.click();
  };

  if (!setup) {
    return (
      <div className="fixed inset-0 z-40 bg-white flex items-center justify-center" data-testid="gig-builder-loading">
        <Spinner size={20} className="animate-spin text-amber-500" />
      </div>
    );
  }

  const s = setup.sections;
  const shell = (id, title, Body) => (
    <SectionShell id={id} title={title}
      locked={setup.locked_sections.includes(id)}
      pending={setup.pending_sections.includes(id)}
      failed={!s[id] && !setup.pending_sections.includes(id)}
      copyValue={s[id] ? copyFor[id](s[id]) : null}
      onRegen={() => regenerate(id)} regenBusy={regen === id} onUpgrade={onUpgrade}>
      {s[id] && Body}
    </SectionShell>
  );
  const L = setup.limits;

  return (
    <div className="fixed inset-0 z-40 bg-zinc-50 overflow-y-auto" data-testid="gig-builder">
      <header className="sticky top-0 z-10 bg-white border-b border-zinc-200">
        <div className="flex items-center justify-between gap-4 px-6 lg:px-8 h-14">
          <button data-testid="gig-builder-close" onClick={onClose}
            className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-zinc-600 hover:text-black">
            <ArrowLeft size={14} weight="bold" /> Dashboard
          </button>
          <div className="flex items-center gap-2">
            {setup.status === "building" && (
              <span data-testid="gig-building-indicator"
                className="flex items-center gap-2 bg-amber-500 text-white font-mono text-[10px] uppercase tracking-[0.2em] px-2 py-1">
                <Spinner size={11} className="animate-spin" /> Writing gig · {setup.pending_sections.length} left
              </span>
            )}
            <button data-testid="gig-download-docx" onClick={download}
              className="flex items-center gap-2 bg-black text-white px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.2em] hover:bg-amber-500 transition-colors">
              <FileDoc size={13} weight="bold" /> Word doc
            </button>
          </div>
        </div>
      </header>

      <div className="px-6 lg:px-8 py-8 max-w-[1400px] mx-auto">
        <div className="mb-8">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-500 flex items-center gap-2">
            <Hammer size={12} weight="bold" /> {setup.kind === "audit" ? "Gig Audit" : "Gig Builder"}
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter mt-1" style={HEAD} data-testid="gig-builder-keyword">
            {setup.keyword}
          </h1>
          <nav className="flex flex-wrap gap-px bg-zinc-200 mt-5 w-fit border border-zinc-200">
            {STEPS.map(([id, n, label]) => (
              <a key={id} href={`#gig-step-${id}`} data-testid={`gig-step-link-${id}`}
                className="bg-white px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] hover:bg-black hover:text-white transition-colors">
                {n} {label}
              </a>
            ))}
          </nav>
        </div>

        {setup.scan_is_stale && (
          <div data-testid="gig-stale-warning" className="mb-6 border border-amber-500 bg-amber-50 p-4 flex items-center justify-between gap-3 flex-wrap">
            <span className="font-mono text-xs flex items-center gap-2">
              <Warning size={14} weight="bold" className="text-amber-600" />
              This scan is {Math.floor(setup.scan_age_days)} days old. Rescan for fresher prices and keywords.
            </span>
            <button data-testid="gig-rescan-btn" onClick={() => onRescan(setup.keyword)}
              className="bg-black text-white px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] hover:bg-amber-500">Rescan</button>
          </div>
        )}

        {setup.audit && (
          <AuditSummary audit={setup.audit} after={setup.score} sectionTitles={s.titles}
            pending={setup.pending_sections.includes("audit")} />
        )}

        <div className="grid lg:grid-cols-[1fr_320px] gap-6 items-start">
          <div className="space-y-10">
            <div id="gig-step-overview" className="space-y-3 scroll-mt-20">
              {shell("titles", "Gig title", <TitlesBody titles={s.titles || []} max={L.title}
                onSave={(i, v) => save("titles", s.titles.map((t, j) => (j === i ? v : t.text)))} />)}
              {shell("category", "Category", <CategoryBody cat={s.category || {}} />)}
              {shell("tags", "Search tags", <TagsBody tags={s.tags || []} maxLen={L.tag} />)}
            </div>
            <div id="gig-step-pricing" className="scroll-mt-20">
              {shell("pricing", "Packages & extras", <PricingBody pricing={s.pricing} limits={L} />)}
            </div>
            <div id="gig-step-content" className="space-y-3 scroll-mt-20">
              {shell("description", "Description", <DescriptionBody text={s.description || ""} max={L.description}
                onSave={(v) => save("description", v)} />)}
              {shell("faq", "FAQ", <FaqBody faq={s.faq || []} />)}
            </div>
            <div id="gig-step-requirements" className="scroll-mt-20">
              {shell("requirements", "Buyer requirements", <RequirementsBody items={s.requirements || []} />)}
            </div>
            <div id="gig-step-gallery" className="scroll-mt-20">
              {shell("gallery", "Gallery file names", <GalleryBody items={s.gallery || []} />)}
            </div>
          </div>
          <aside className="lg:sticky lg:top-20">
            <Checklist checklist={setup.checklist} score={setup.score} />
          </aside>
        </div>
      </div>
    </div>
  );
};
