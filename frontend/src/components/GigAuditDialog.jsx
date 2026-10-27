import React, { useEffect, useState } from "react";
import { MagnifyingGlassPlus } from "@phosphor-icons/react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { useAuth } from "../AuthContext";

const TIERS = ["Basic", "Standard", "Premium"];
const emptyPkgs = () => TIERS.map((tier) => ({ tier, name: "", description: "", price: "", delivery_days: "" }));
const inputCls = "w-full border border-zinc-300 px-3 py-2 font-mono text-xs outline-none focus:border-black bg-white";
const Label = ({ children }) => (
  <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500 mb-1">{children}</div>
);

const parseFaq = (text) =>
  text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean).map((b) => {
    const [q, ...rest] = b.split("\n");
    return { question: q.replace(/^q[:.]\s*/i, "").trim(), answer: rest.join(" ").replace(/^a[:.]\s*/i, "").trim() };
  }).filter((f) => f.question && f.answer);

const PackagesInput = ({ pkgs, setPkgs }) => {
  const set = (i, k, v) => setPkgs(pkgs.map((p, j) => (j === i ? { ...p, [k]: v } : p)));
  return (
    <div className="grid grid-cols-3 gap-2">
      {pkgs.map((p, i) => (
        <div key={p.tier} className="space-y-1" data-testid={`audit-package-${p.tier.toLowerCase()}`}>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em]">{p.tier}</div>
          <input className={inputCls} placeholder="Name" value={p.name} onChange={(e) => set(i, "name", e.target.value)}
            data-testid={`audit-package-name-${p.tier.toLowerCase()}`} />
          <input className={inputCls} placeholder="Short description" value={p.description}
            onChange={(e) => set(i, "description", e.target.value)} data-testid={`audit-package-desc-${p.tier.toLowerCase()}`} />
          <div className="flex gap-1">
            <input className={inputCls} placeholder="$ price" type="number" min="0" value={p.price}
              onChange={(e) => set(i, "price", e.target.value)} data-testid={`audit-package-price-${p.tier.toLowerCase()}`} />
            <input className={inputCls} placeholder="days" type="number" min="0" value={p.delivery_days}
              onChange={(e) => set(i, "delivery_days", e.target.value)} data-testid={`audit-package-days-${p.tier.toLowerCase()}`} />
          </div>
        </div>
      ))}
    </div>
  );
};

export const GigAuditDialog = ({ open, onOpenChange, onStarted, onNeedScan }) => {
  const { authAxios } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [description, setDescription] = useState("");
  const [pkgs, setPkgs] = useState(emptyPkgs);
  const [faq, setFaq] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    authAxios.get("/scrape/jobs").then((r) => {
      const seen = new Set();
      setJobs(r.data.filter((j) => j.status === "complete" && !seen.has(j.keyword.toLowerCase()) && seen.add(j.keyword.toLowerCase())));
    }).catch(() => setJobs([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = async () => {
    if (!jobId) return toast.error("Pick a scanned keyword to target");
    if (title.trim().length < 5) return toast.error("Paste your gig title");
    setBusy(true);
    try {
      const r = await authAxios.post("/gigs/audit", {
        job_id: jobId,
        original: {
          title, description,
          tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
          packages: pkgs.filter((p) => p.name || p.price).map((p) => ({
            ...p, price: p.price === "" ? null : Number(p.price),
            delivery_days: p.delivery_days === "" ? null : Number(p.delivery_days),
          })),
          faq: parseFaq(faq),
        },
      });
      onStarted(r.data.id);
      setTitle(""); setTags(""); setDescription(""); setPkgs(emptyPkgs()); setFaq("");
    } catch (e) {
      toast.error(e?.response?.status === 422 ? "Check the gig fields — something is too long or empty" : "Could not start the audit");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl rounded-none border-zinc-200 p-0 gap-0 max-h-[92vh] overflow-y-auto" data-testid="gig-audit-dialog">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-zinc-200">
          <DialogTitle className="text-2xl font-black tracking-tighter flex items-center gap-2" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
            <MagnifyingGlassPlus size={20} weight="bold" className="text-amber-500" /> Gig Audit
          </DialogTitle>
          <DialogDescription className="text-xs font-mono text-zinc-500">
            Paste your existing gig. We score it, list what's hurting its ranking and rewrite it for a scanned keyword.
          </DialogDescription>
        </DialogHeader>
        <div className="p-6 space-y-5">
          <div>
            <Label>Target keyword (from your scans)</Label>
            {jobs.length === 0 ? (
              <div className="flex items-center justify-between border border-amber-500 bg-amber-50 p-3 font-mono text-xs" data-testid="audit-no-scans">
                No scanned keywords yet.
                <button onClick={onNeedScan} className="underline font-bold" data-testid="audit-go-scan-btn">Scan one first</button>
              </div>
            ) : (
              <Select value={jobId} onValueChange={setJobId}>
                <SelectTrigger className="rounded-none font-mono text-xs" data-testid="audit-keyword-select">
                  <SelectValue placeholder="Pick a keyword" />
                </SelectTrigger>
                <SelectContent>
                  {jobs.map((j) => (
                    <SelectItem key={j.id} value={j.id} data-testid={`audit-keyword-option-${j.id}`}>{j.keyword}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <div>
            <Label>Gig title</Label>
            <div className="flex items-center border border-zinc-300 focus-within:border-black">
              <span className="pl-3 font-mono text-xs text-zinc-400">I will</span>
              <input className="flex-1 px-2 py-2 font-mono text-xs outline-none" value={title}
                onChange={(e) => setTitle(e.target.value)} data-testid="audit-title-input" placeholder="design a modern logo for your business" />
            </div>
          </div>
          <div>
            <Label>Tags (comma separated)</Label>
            <input className={inputCls} value={tags} onChange={(e) => setTags(e.target.value)} data-testid="audit-tags-input"
              placeholder="logo design, minimalist logo, brand logo" />
          </div>
          <div>
            <Label>Description</Label>
            <textarea rows={6} className={inputCls} value={description} onChange={(e) => setDescription(e.target.value)}
              data-testid="audit-description-input" />
          </div>
          <div>
            <Label>Packages (optional)</Label>
            <PackagesInput pkgs={pkgs} setPkgs={setPkgs} />
          </div>
          <div>
            <Label>FAQ (optional — question on the first line, answer below, blank line between items)</Label>
            <textarea rows={4} className={inputCls} value={faq} onChange={(e) => setFaq(e.target.value)} data-testid="audit-faq-input" />
          </div>
          <button onClick={submit} disabled={busy || jobs.length === 0} data-testid="audit-submit-btn"
            className="w-full bg-black text-white py-3 font-mono text-xs uppercase tracking-[0.25em] hover:bg-amber-500 transition-colors disabled:opacity-50">
            {busy ? "Starting audit…" : "Audit & rewrite my gig"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
