import React, { useEffect, useState } from "react";
import { Crown } from "@phosphor-icons/react";
import { CopyButton, Counter } from "./parts";

const TitleRow = ({ t, i, max, onSave }) => {
  const [val, setVal] = useState(t.text);
  useEffect(() => setVal(t.text), [t.text]);
  return (
    <div data-testid={`gig-title-option-${i}`}
      className={`border p-3 ${i === 0 ? "border-amber-500 bg-amber-50/40" : "border-zinc-200"}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-1">
          {i === 0 && <Crown size={11} weight="fill" className="text-amber-500" />}
          Option {i + 1} · {t.coverage} keyword{t.coverage === 1 ? "" : "s"} covered
        </span>
        <div className="flex items-center gap-2">
          <Counter value={val.length} max={max} testid={`gig-title-counter-${i}`} />
          <CopyButton text={`I will ${val}`} testid={`gig-title-copy-${i}`} />
        </div>
      </div>
      <div className="flex items-baseline gap-2 font-mono text-sm">
        <span className="text-zinc-400 shrink-0 select-none">I will</span>
        <input data-testid={`gig-title-input-${i}`} value={val} onChange={(e) => setVal(e.target.value)}
          onBlur={() => val !== t.text && onSave(i, val)}
          className={`flex-1 bg-transparent outline-none border-b ${val.length > max ? "border-red-500" : "border-transparent focus:border-black"}`} />
      </div>
    </div>
  );
};

export const TitlesBody = ({ titles, max, onSave }) => (
  <div className="space-y-2">
    {titles.map((t, i) => <TitleRow key={i} t={t} i={i} max={max} onSave={onSave} />)}
  </div>
);

export const CategoryBody = ({ cat }) => (
  <div className="flex flex-wrap items-center gap-2 font-mono text-sm" data-testid="gig-category-value">
    {[cat.category, cat.subcategory, cat.service_type].filter((c, i, arr) => c && arr.indexOf(c) === i).map((c, i, arr) => (
      <React.Fragment key={i}>
        <span className="border border-zinc-300 px-2 py-1">{c}</span>
        {i < arr.length - 1 && <span className="text-zinc-400">›</span>}
      </React.Fragment>
    ))}
  </div>
);

export const TagsBody = ({ tags, maxLen }) => (
  <div className="flex flex-wrap gap-2">
    {tags.map((t, i) => (
      <div key={i} data-testid={`gig-tag-${i}`} className="flex items-center gap-2 border border-black pl-3 pr-1 py-1">
        <span className="font-mono text-xs">{t}</span>
        <Counter value={t.length} max={maxLen} testid={`gig-tag-counter-${i}`} />
        <CopyButton text={t} testid={`gig-tag-copy-${i}`} />
      </div>
    ))}
  </div>
);
