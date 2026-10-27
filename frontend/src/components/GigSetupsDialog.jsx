import React, { useEffect, useState } from "react";
import { Trash, Hammer } from "@phosphor-icons/react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { useAuth } from "../AuthContext";

export const GigSetupsDialog = ({ open, onOpenChange, onOpenSetup }) => {
  const { authAxios } = useAuth();
  const [items, setItems] = useState(null);

  useEffect(() => {
    if (!open) return;
    authAxios.get("/gigs").then((r) => setItems(r.data.items)).catch(() => setItems([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const remove = async (id) => {
    await authAxios.delete(`/gigs/${id}`);
    setItems((xs) => xs.filter((x) => x.id !== id));
    toast.success("Gig setup deleted");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl rounded-none border-zinc-200 p-0 gap-0" data-testid="gig-setups-dialog">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-zinc-200">
          <DialogTitle className="text-2xl font-black tracking-tighter" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
            My Gig Setups
          </DialogTitle>
          <DialogDescription className="text-xs font-mono text-zinc-500">
            Every gig you build is saved here. Open one to copy, edit or download it.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-y-auto divide-y divide-zinc-100" data-testid="gig-setups-list">
          {items === null && <p className="p-6 font-mono text-xs text-zinc-400">Loading…</p>}
          {items?.length === 0 && (
            <p className="p-6 font-mono text-xs text-zinc-400" data-testid="gig-setups-empty">
              No gig setups yet. Scan a keyword and hit Build Gig.
            </p>
          )}
          {items?.map((g) => (
            <div key={g.id} className="flex items-center gap-3 px-6 py-3 hover:bg-zinc-50" data-testid={`gig-setup-row-${g.id}`}>
              <Hammer size={14} weight="bold" className="text-amber-500 shrink-0" />
              <button onClick={() => onOpenSetup(g.id)} data-testid={`gig-setup-open-${g.id}`} className="flex-1 text-left min-w-0">
                <div className="font-mono text-sm font-bold truncate">{g.keyword}</div>
                <div className="font-mono text-[11px] text-zinc-500 truncate">{g.title ? `I will ${g.title}` : "Building…"}</div>
              </button>
              <span className="font-mono text-[10px] text-zinc-400 shrink-0">{new Date(g.updated_at).toLocaleDateString()}</span>
              <button onClick={() => remove(g.id)} data-testid={`gig-setup-delete-${g.id}`} className="text-zinc-400 hover:text-red-500">
                <Trash size={14} weight="bold" />
              </button>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};
