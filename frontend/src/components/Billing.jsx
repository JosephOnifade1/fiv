import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../components/ui/dialog";
import { Check, Lightning, Crown, Spinner } from "@phosphor-icons/react";
import { toast } from "sonner";

const FEATURES_FREE = [
  "5 niche scans / month",
  "Opportunity Score & Ratio Gold",
  "Top 10 / Bottom 10 gigs",
  "Basic AI summary & expansions",
];
const FEATURES_PRO = [
  "Unlimited niche scans",
  "All 2026 reverse-engineering metrics",
  "AI Trend Verdict + Proximity Map",
  "Live Fiverr autocomplete tap",
  "Watchlist + week-over-week trends",
  "CSV / JSON exports",
  "Priority queue + email alerts (coming soon)",
];

export const PricingDialog = ({ open, onOpenChange, billing, onRefresh }) => {
  const { authAxios } = useAuth();
  const [busy, setBusy] = useState(false);

  const upgrade = async () => {
    setBusy(true);
    try {
      const r = await authAxios.post("/billing/checkout", {
        package_id: "pro_monthly",
        origin_url: window.location.origin,
      });
      window.location.href = r.data.url;
    } catch (e) {
      toast.error("Could not start checkout");
      setBusy(false);
    }
  };

  const isPro = billing?.plan === "pro";
  const isAdmin = billing?.is_admin;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl rounded-none border-zinc-200 p-0 gap-0" data-testid="pricing-dialog">
        <DialogHeader className="px-8 pt-8 pb-4 border-b border-zinc-200">
          <DialogTitle className="text-3xl font-black tracking-tighter" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
            Choose your operator tier
          </DialogTitle>
          <DialogDescription className="text-xs font-mono text-zinc-500 mt-1">
            {isAdmin ? "Admin override active. Unlimited access granted." :
              isPro ? "You're on Pro. Manage anytime." : "Upgrade to unlock the full 2026 algorithm signal."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid sm:grid-cols-2">
          {/* FREE */}
          <div className="p-8 border-r border-zinc-200" data-testid="plan-free">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Free</div>
            <div className="mt-2 text-5xl font-black tracking-tighter font-mono">$0</div>
            <div className="text-[10px] font-mono text-zinc-400 uppercase tracking-[0.2em]">forever</div>
            <ul className="mt-6 space-y-2.5">
              {FEATURES_FREE.map((f) => (
                <li key={f} className="text-xs font-mono flex gap-2"><Check size={12} weight="bold" className="text-zinc-400 mt-0.5" /> {f}</li>
              ))}
            </ul>
            {!isPro && (
              <div className="mt-6 text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500">
                {billing?.scans_used_this_month ?? 0} / {billing?.free_limit ?? 5} scans used this month
              </div>
            )}
          </div>

          {/* PRO */}
          <div className="p-8 bg-zinc-50 relative" data-testid="plan-pro">
            <div className="absolute top-4 right-4 text-[9px] uppercase tracking-[0.2em] font-mono bg-amber-500 text-white px-2 py-0.5">
              Recommended
            </div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-amber-600 flex items-center gap-1">
              <Crown size={11} weight="fill" /> Pro
            </div>
            <div className="mt-2 flex items-baseline gap-1">
              <span className="text-5xl font-black tracking-tighter font-mono">${billing?.price_usd ?? 29}</span>
              <span className="text-xs font-mono text-zinc-500">/ month</span>
            </div>
            <div className="text-[10px] font-mono text-zinc-400 uppercase tracking-[0.2em]">renews monthly</div>
            <ul className="mt-6 space-y-2.5">
              {FEATURES_PRO.map((f) => (
                <li key={f} className="text-xs font-mono flex gap-2"><Check size={12} weight="bold" className="text-amber-500 mt-0.5" /> {f}</li>
              ))}
            </ul>
            <Button
              data-testid="upgrade-btn"
              disabled={busy || isPro}
              onClick={upgrade}
              className="mt-6 w-full rounded-none bg-black hover:bg-zinc-800 text-white font-mono text-xs uppercase tracking-[0.2em] h-11"
            >
              {busy ? <Spinner size={14} className="animate-spin mr-2" /> : <Lightning size={14} weight="bold" className="mr-2" />}
              {isAdmin ? "Admin Pro Active" : isPro ? "Pro Active" : busy ? "Redirecting…" : "Upgrade to Pro"}
            </Button>
            <p className="text-[10px] font-mono text-zinc-400 mt-3 text-center">
              Secure checkout via Stripe · cancel anytime
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const PlanBadge = ({ billing, onOpen }) => {
  if (!billing) return null;
  const isPro = billing.plan === "pro";
  const remaining = billing.scans_remaining;
  return (
    <button
      onClick={onOpen}
      data-testid="plan-badge"
      className={`text-[10px] uppercase tracking-[0.2em] font-mono px-3 py-1.5 border transition-colors ${
        isPro
          ? "bg-black text-amber-400 border-black"
          : remaining === 0
          ? "bg-red-50 text-red-700 border-red-300 hover:bg-red-100"
          : "bg-white text-zinc-700 border-zinc-300 hover:border-black"
      }`}
    >
      {isPro ? (
        <span className="flex items-center gap-1.5">
          <Crown size={11} weight="fill" /> {billing.is_admin ? "ADMIN · PRO" : "PRO"}
        </span>
      ) : (
        <span>{`FREE · ${billing.scans_used_this_month}/${billing.free_limit}`}</span>
      )}
    </button>
  );
};

/** Hook returns: { billing, refresh, pollAfterCheckout, openPricing, PricingMount } */
export const useBilling = () => {
  const { authAxios, token } = useAuth();
  const [billing, setBilling] = useState(null);
  const [open, setOpen] = useState(false);

  const refresh = async () => {
    if (!token) return null;
    try {
      const r = await authAxios.get("/billing/me");
      setBilling(r.data);
      return r.data;
    } catch { return null; }
  };

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [token]);

  // Handle Stripe redirect: ?session_id=...
  useEffect(() => {
    const url = new URL(window.location.href);
    const sid = url.searchParams.get("session_id");
    if (!sid || !token) return;
    let cancelled = false;
    let attempts = 0;
    const poll = async () => {
      attempts++;
      if (cancelled || attempts > 8) return;
      try {
        const r = await authAxios.get(`/billing/status/${sid}`);
        if (r.data.payment_status === "paid") {
          toast.success("Pro activated — unlimited scans unlocked.");
          await refresh();
          url.searchParams.delete("session_id");
          window.history.replaceState({}, "", url.pathname + url.search);
          return;
        }
        if (r.data.status === "expired") {
          toast.error("Checkout expired. Try again.");
          url.searchParams.delete("session_id");
          window.history.replaceState({}, "", url.pathname + url.search);
          return;
        }
      } catch {/* noop */}
      setTimeout(poll, 2000);
    };
    poll();
    return () => { cancelled = true; };
    // eslint-disable-next-line
  }, [token]);

  const PricingMount = (
    <PricingDialog open={open} onOpenChange={setOpen} billing={billing} onRefresh={refresh} />
  );

  return { billing, refresh, openPricing: () => setOpen(true), PricingMount };
};
