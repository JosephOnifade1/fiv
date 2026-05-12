import React, { useState, useEffect, useRef } from "react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { MagnifyingGlass, Lightning, Graph } from "@phosphor-icons/react";

export const SearchBar = ({ value, onChange, onSubmit, busy, authAxios }) => {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const timer = useRef(null);
  const wrap = useRef(null);

  useEffect(() => {
    clearTimeout(timer.current);
    if (!value || value.length < 2) {
      setSuggestions([]);
      return;
    }
    timer.current = setTimeout(async () => {
      try {
        const r = await authAxios.post("/autocomplete", { query: value });
        setSuggestions(r.data.suggestions || []);
        setOpen(true);
        setHighlight(-1);
      } catch {/* noop */}
    }, 350);
    return () => clearTimeout(timer.current);
  }, [value, authAxios]);

  useEffect(() => {
    const close = (e) => {
      if (wrap.current && !wrap.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (s) => {
    onChange(s);
    setOpen(false);
    setTimeout(() => onSubmit(s), 0);
  };

  const keyHandler = (e) => {
    if (!open || suggestions.length === 0) {
      if (e.key === "Enter") onSubmit();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(suggestions.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(-1, h - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlight >= 0) pick(suggestions[highlight]);
      else onSubmit();
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative" ref={wrap}>
      <div className="border border-zinc-200 bg-white">
        <div className="flex items-center gap-2 p-2">
          <MagnifyingGlass size={18} weight="bold" className="ml-3 text-zinc-400" />
          <Input
            data-testid="search-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={keyHandler}
            onFocus={() => suggestions.length > 0 && setOpen(true)}
            placeholder='e.g. "logo for bio-hacking startups"'
            className="border-0 rounded-none focus-visible:ring-0 h-11 font-mono text-sm flex-1"
            autoComplete="off"
          />
          <Button onClick={() => onSubmit()} disabled={busy}
            data-testid="search-submit"
            className="rounded-none bg-black hover:bg-zinc-800 text-white font-mono text-xs uppercase tracking-[0.2em] h-11 px-6">
            <Lightning size={14} weight="bold" className="mr-2" />
            {busy ? "Scanning..." : "Scan"}
          </Button>
        </div>
        {busy && (
          <div className="h-1 bg-zinc-100 overflow-hidden">
            <div className="h-full bg-amber-500 animate-pulse" style={{ width: "60%" }} />
          </div>
        )}
      </div>

      {open && suggestions.length > 0 && (
        <div data-testid="autocomplete-dropdown"
          className="absolute z-30 left-0 right-0 mt-1 border border-zinc-200 bg-white shadow-[0_2px_24px_-12px_rgba(0,0,0,0.25)]">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-200 bg-zinc-50">
            <Graph size={12} weight="bold" />
            <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
              Fiverr Autocomplete · Pre-validated demand
            </span>
          </div>
          {suggestions.map((s, i) => (
            <button
              key={s}
              data-testid={`autocomplete-suggestion-${i}`}
              onMouseDown={() => pick(s)}
              onMouseEnter={() => setHighlight(i)}
              className={`w-full text-left text-xs font-mono px-4 py-2 border-b border-zinc-100 last:border-b-0 transition-colors ${
                i === highlight ? "bg-black text-white" : "bg-white hover:bg-zinc-50"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
