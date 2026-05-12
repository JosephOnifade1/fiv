import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { ShareNetwork, Copy, Gift } from "@phosphor-icons/react";
import { toast } from "sonner";

export const ReferralDialog = ({ open, onOpenChange, onRedeemSuccess }) => {
  const { authAxios } = useAuth();
  const [data, setData] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    authAxios.get("/referral/code").then((r) => setData(r.data)).catch(() => {});
  }, [open, authAxios]);

  const copy = () => {
    const url = `${window.location.origin}${data?.share_url}`;
    navigator.clipboard.writeText(url);
    toast.success("Referral link copied");
  };

  const redeem = async () => {
    if (!code.trim()) return;
    setBusy(true);
    try {
      const r = await authAxios.post("/referral/redeem", { code: code.trim() });
      toast.success(`Pro extended by ${r.data.granted_days} days`);
      setCode("");
      onRedeemSuccess?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not redeem code");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg rounded-none border-zinc-200 p-0 gap-0" data-testid="referral-dialog">
        <DialogHeader className="px-7 pt-7 pb-3 border-b border-zinc-200">
          <DialogTitle className="text-2xl font-black tracking-tighter flex items-center gap-2"
            style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
            <Gift size={20} weight="duotone" /> Referral
          </DialogTitle>
          <DialogDescription className="text-xs font-mono text-zinc-500 mt-1">
            Share Fiverr Scout. You both get 1 month of Pro when they join.
          </DialogDescription>
        </DialogHeader>
        <div className="p-7 space-y-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500 mb-2">Your code</div>
            <div className="flex items-center gap-2">
              <div className="border border-zinc-200 bg-zinc-50 px-4 py-3 font-mono text-base font-black flex-1" data-testid="referral-code">
                {data?.code || "…"}
              </div>
              <Button onClick={copy} disabled={!data}
                data-testid="referral-copy"
                className="rounded-none bg-black hover:bg-zinc-800 text-white font-mono text-xs uppercase tracking-[0.15em] h-12 px-4">
                <ShareNetwork size={12} weight="bold" className="mr-1.5" /> Copy link
              </Button>
            </div>
            <p className="text-[10px] font-mono text-zinc-400 mt-2">
              {data?.redemptions || 0} friends have joined via your code.
            </p>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500 mb-2">Redeem a code</div>
            <div className="flex gap-2">
              <Input
                data-testid="referral-redeem-input"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="FS-XXXXXXXX"
                className="rounded-none border-zinc-300 focus-visible:ring-0 focus-visible:border-black h-11 font-mono uppercase tracking-[0.1em]"
              />
              <Button onClick={redeem} disabled={busy || !code.trim()}
                data-testid="referral-redeem-btn"
                className="rounded-none bg-amber-500 hover:bg-amber-600 text-white font-mono text-xs uppercase tracking-[0.15em] h-11 px-4">
                {busy ? "..." : "Redeem"}
              </Button>
            </div>
            <p className="text-[10px] font-mono text-zinc-400 mt-2">
              Each user can redeem one referral code. Adds 30 days of Pro to your account.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
