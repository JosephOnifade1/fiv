import React, { useEffect, useState } from "react";
import { Crown } from "@phosphor-icons/react";
import { CopyButton, Counter } from "./parts";

const pkgText = (p) =>
  `${p.tier} — ${p.name}\n${p.description}\nDelivery: ${p.delivery_days} days · Revisions: ${p.revisions}\n` +
  `${p.included.map((i) => `• ${i}`).join("\n")}\nPrice: $${p.price}`;

export const pricingText = (pr) =>
  pr.packages.map(pkgText).join("\n\n") +
  (pr.extras?.length ? `\n\nExtras:\n${pr.extras.map((e) => `• ${e.name} (+$${e.price}) — ${e.description}`).join("\n")}` : "");

export const PricingBody = ({ pricing, limits }) => (
  <div className="space-y-4">
    <div className="grid md:grid-cols-3 gap-px bg-zinc-200 border border-zinc-200">
      {pricing.packages.map((p, i) => (
        <div key={p.tier} data-testid={`gig-package-${p.tier.toLowerCase()}`}
          className={`p-4 space-y-2 ${i === 1 ? "bg-amber-50/50" : "bg-white"}`}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500 flex items-center gap-1">
              {i === 1 && <Crown size={11} weight="fill" className="text-amber-500" />}{p.tier}
            </span>
            <CopyButton text={pkgText(p)} testid={`gig-package-copy-${p.tier.toLowerCase()}`} />
          </div>
          <div className="text-3xl font-black tracking-tighter" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}
            data-testid={`gig-package-price-${p.tier.toLowerCase()}`}>${p.price}</div>
          <div className="font-bold text-sm">{p.name} <Counter value={p.name.length} max={limits.package_name} /></div>
          <p className="font-mono text-xs text-zinc-600">{p.description} <Counter value={p.description.length} max={limits.package_description} /></p>
          <div className="font-mono text-[11px] text-zinc-500">{p.delivery_days}d delivery · {p.revisions} revisions</div>
          <ul className="font-mono text-[11px] space-y-1">{p.included.map((x, j) => <li key={j}>▸ {x}</li>)}</ul>
        </div>
      ))}
    </div>
    <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]" data-testid="gig-price-anchors">
      Niche median ${pricing.anchors?.median} · top decile ${pricing.anchors?.top_decile}
    </div>
    {pricing.extras?.length > 0 && (
      <div className="space-y-2">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500">Gig extras</div>
        {pricing.extras.map((e, i) => (
          <div key={i} data-testid={`gig-extra-${i}`} className="flex items-center justify-between gap-3 border border-zinc-200 px-3 py-2">
            <span className="font-mono text-xs"><b>{e.name}</b> · +${e.price} — {e.description}</span>
            <CopyButton text={`${e.name} (+$${e.price}) — ${e.description}`} testid={`gig-extra-copy-${i}`} />
          </div>
        ))}
      </div>
    )}
  </div>
);

export const DescriptionBody = ({ text, max, onSave }) => {
  const [val, setVal] = useState(text);
  useEffect(() => setVal(text), [text]);
  return (
    <div className="space-y-2">
      <textarea data-testid="gig-description-input" value={val} onChange={(e) => setVal(e.target.value)}
        onBlur={() => val !== text && onSave(val)} rows={14}
        className={`w-full font-mono text-xs leading-relaxed border p-3 outline-none resize-y ${val.length > max ? "border-red-500" : "border-zinc-200 focus:border-black"}`} />
      <div className="text-right"><Counter value={val.length} max={max} testid="gig-description-counter" /></div>
    </div>
  );
};

export const FaqBody = ({ faq }) => (
  <div className="divide-y divide-zinc-100 border border-zinc-200">
    {faq.map((f, i) => (
      <div key={i} data-testid={`gig-faq-${i}`} className="p-3 flex gap-3 justify-between">
        <div>
          <div className="font-bold text-sm">{f.question}</div>
          <p className="font-mono text-xs text-zinc-600 mt-1 leading-relaxed">{f.answer}</p>
        </div>
        <CopyButton text={`${f.question}\n${f.answer}`} testid={`gig-faq-copy-${i}`} />
      </div>
    ))}
  </div>
);
