"use client";

import { useRef, type PointerEvent } from "react";
import { scaleLinear } from "d3-scale";
import { isoToMs, type Cell, type MonthBar, type YearBar } from "@/lib/derive";
import type { Erosion, Merck } from "@/lib/schema";
import { count, int, longDate, rate, shortDate, signedUsd } from "@/lib/format";
import { Tip, niceTicks, roundedBar, useTip, useWidth } from "./chart";

// ------------------------------------------------------------------------------------------ January: 12 bars

export function SeasonBars({ bars }: { bars: MonthBar[] }) {
  const [wrap, width] = useWidth<HTMLDivElement>(900);
  const host = useRef<HTMLDivElement | null>(null);
  const { tip, atElement, hide } = useTip(host);
  const h = width < 560 ? 220 : 260;
  const m = { top: 28, right: 8, bottom: 30, left: 8 };
  const iw = width - m.left - m.right;
  const ih = h - m.top - m.bottom;
  const max = Math.max(...bars.map((b) => b.share));
  const y = scaleLinear().domain([0, max * 1.08]).range([ih, 0]);
  const slot = iw / bars.length;
  const bw = Math.min(56, slot * 0.66);
  return (
    <div ref={host} style={{ position: "relative" }}>
      <div ref={wrap}>
        <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label="Brand price rises of 2% or more by calendar month, as a share of all of them. January is the tallest.">
          <g transform={`translate(${m.left},${m.top})`}>
            <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            {bars.map((b, i) => {
              const x = i * slot + (slot - bw) / 2;
              const jan = b.m === 1;
              const july = b.m === 7;
              const bh = ih - y(b.share);
              return (
                <g
                  key={b.m}
                  tabIndex={0}
                  onPointerEnter={atElement(b.name, [{ label: "Rises of 2% or more", value: int(b.n) }, { label: "Share of all", value: `${(b.share * 100).toFixed(1)}%` }])}
                  onFocus={atElement(b.name, [{ label: "Rises of 2% or more", value: int(b.n) }, { label: "Share of all", value: `${(b.share * 100).toFixed(1)}%` }])}
                  onPointerLeave={hide}
                  onBlur={hide}
                  aria-label={`${b.name}: ${(b.share * 100).toFixed(1)}% of brand rises of 2% or more`}
                >
                  <path className={jan ? "bar-d" : "bar-m"} d={roundedBar(x, y(b.share), bw, bh, 3, "up")} />
                  <text x={x + bw / 2} y={y(b.share) - 7} textAnchor="middle" className={jan ? "t-denim" : july ? "t-strong" : "t-mute"} fontWeight={jan || july ? 600 : 400}>
                    {(b.share * 100).toFixed(1)}%
                  </text>
                  <text x={x + bw / 2} y={ih + 19} textAnchor="middle" className={july ? "t-strong" : "t-mute"} fontWeight={july ? 600 : 400}>
                    {width < 560 ? b.name.slice(0, 1) : b.name.slice(0, 3)}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      <Tip tip={tip} width={width} />
    </div>
  );
}

// ------------------------------------------------------------------------------------------ rises per year

export function YearBars({ bars }: { bars: YearBar[] }) {
  const [wrap, width] = useWidth<HTMLDivElement>(560);
  const h = 230;
  const m = { top: 24, right: 6, bottom: 28, left: 6 };
  const iw = width - m.left - m.right;
  const ih = h - m.top - m.bottom;
  const { top } = niceTicks(Math.max(...bars.map((b) => b.n)), 4);
  const y = scaleLinear().domain([0, top]).range([ih, 0]);
  const slot = iw / bars.length;
  const bw = Math.min(30, slot * 0.7);
  return (
    <div ref={wrap}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label="Brand price rises of 2% or more per year, 2013 to 2026">
        <defs>
          <pattern id="hatch-y" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="4" height="4" fill="var(--paper)" />
            <line x1="0" y1="0" x2="0" y2="4" stroke="var(--ink-3)" strokeWidth="1" />
          </pattern>
        </defs>
        <g transform={`translate(${m.left},${m.top})`}>
          <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
          {bars.map((b, i) => {
            const x = i * slot + (slot - bw) / 2;
            return (
              <g key={b.y}>
                <path d={roundedBar(x, y(b.n), bw, ih - y(b.n), 3, "up")} className={b.partial ? "" : "bar-m"} fill={b.partial ? "url(#hatch-y)" : undefined} stroke={b.partial ? "var(--ink-3)" : undefined} strokeWidth={b.partial ? 1 : undefined} />
                <text x={x + bw / 2} y={y(b.n) - 6} textAnchor="middle" className="t-mute">
                  {count(b.n)}
                </text>
                <text x={x + bw / 2} y={ih + 18} textAnchor="middle" className="t-mute">
                  {width < 480 ? String(b.y).slice(2) : b.y}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ erosion

export function ErosionChart({ erosion, spendQ4, spendQ8, molecules }: { erosion: Erosion; spendQ4: number | null; spendQ8: number | null; molecules: { brand: number; generic: number } }) {
  const [wrap, width] = useWidth<HTMLDivElement>(900);
  const host = useRef<HTMLDivElement | null>(null);
  const { tip, atElement, hide } = useTip(host);
  const narrow = width < 640;
  const m = { top: 16, right: narrow ? 70 : 200, bottom: 40, left: 34 };
  const h = narrow ? 300 : 360;
  const iw = width - m.left - m.right;
  const ih = h - m.top - m.bottom;
  const x = scaleLinear().domain([-8, 12]).range([0, iw]);
  const y = scaleLinear().domain([0, 125]).range([ih, 0]);
  const brand = erosion.cohort.brand.filter((b) => b.median != null);
  const generic = erosion.cohort.generic.filter((b) => b.median != null);
  const line = (rows: { k: number; median: number | null }[]) => rows.map((r, i) => `${i ? "L" : "M"}${x(r.k).toFixed(1)},${y(r.median as number).toFixed(1)}`).join(" ");
  const band =
    generic.length > 1
      ? generic.map((r, i) => `${i ? "L" : "M"}${x(r.k).toFixed(1)},${y(r.p75 as number).toFixed(1)}`).join(" ") +
        " " +
        [...generic].reverse().map((r) => `L${x(r.k).toFixed(1)},${y(r.p25 as number).toFixed(1)}`).join(" ") +
        " Z"
      : "";
  const b8 = brand.find((b) => b.k === 8);
  const g8 = generic.find((b) => b.k === 8);
  const spend = [
    { k: 4, v: spendQ4 },
    { k: 8, v: spendQ8 },
  ].filter((s) => s.v != null) as { k: number; v: number }[];
  return (
    <div ref={host} style={{ position: "relative" }}>
      <div ref={wrap}>
        <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={`Median brand price, generic price and brand Medicaid spend after the first generic is priced. Brand price stays near ${b8?.median?.toFixed(0)} while brand spend falls to ${spendQ8?.toFixed(0)}.`}>
          <g transform={`translate(${m.left},${m.top})`}>
            {[0, 25, 50, 75, 100, 125].map((t) => (
              <g key={t}>
                <line className={t === 100 ? "base" : "grid"} x1={0} x2={iw} y1={y(t)} y2={y(t)} />
                <text className="t-mute" x={-8} y={y(t) + 4} textAnchor="end">
                  {t}
                </text>
              </g>
            ))}
            <line className="jan-rule" x1={x(0)} x2={x(0)} y1={0} y2={ih + 6} />
            <text className="t-mute" x={x(0) + 6} y={14}>
              first generic priced
            </text>
            {[-8, -4, 0, 4, 8, 12].map((k) => (
              <text key={k} className="t-mute" x={x(k)} y={ih + 24} textAnchor="middle">
                {k}
              </text>
            ))}
            <text className="t-mute" x={iw / 2} y={ih + 38} textAnchor="middle">
              quarters since the first generic was priced
            </text>
            <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            {band && <path className="band-f" d={band} />}
            <path className="l-mute" d={line(generic)} />
            <path className="l-ink" d={line(brand)} />
            {spend.map((s) => (
              <g
                key={s.k}
                tabIndex={0}
                onPointerEnter={atElement(`Brand Medicaid spend, quarter ${s.k}`, [{ label: "Index", value: s.v.toFixed(1) }, { label: "Molecules", value: String(s.k === 4 ? erosion.spendMedian.eventsQ4 : erosion.spendMedian.eventsQ8) }])}
                onFocus={atElement(`Brand Medicaid spend, quarter ${s.k}`, [{ label: "Index", value: s.v.toFixed(1) }])}
                onPointerLeave={hide}
                onBlur={hide}
                aria-label={`Brand Medicaid spend at quarter ${s.k}: ${s.v.toFixed(1)}`}
              >
                <rect className="mk-i" x={x(s.k) - 5} y={y(s.v) - 5} width={10} height={10} rx={1} />
                <text className="t-strong" x={x(s.k) + 10} y={y(s.v) + 4}>
                  {s.v.toFixed(1)}
                </text>
              </g>
            ))}
            {b8?.median != null && (
              <text className="t-strong" x={x(8) + 8} y={y(b8.median) - 8}>
                Brand price {b8.median.toFixed(1)}
              </text>
            )}
            {g8?.median != null && (
              <text className="t-lab" x={x(8) + 8} y={y(g8.median) + 16}>
                Generic price {g8.median.toFixed(1)}
              </text>
            )}
            {!narrow && (
              <g>
                <text className="t-lab" x={iw + 14} y={y(brand[brand.length - 1]?.median ?? 100) - 6}>
                  Brand price
                </text>
                <text className="t-lab" x={iw + 14} y={y(generic[generic.length - 1]?.median ?? 50) + 4}>
                  Generic price
                </text>
              </g>
            )}
          </g>
        </svg>
      </div>
      <p className="src" style={{ marginTop: 6 }}>
        Brand price: {molecules.brand} molecules with priced brand packs (100 = the quarter before entry). Generic price: {molecules.generic} molecules (100 = each pack&apos;s launch price).
        Brand spend: Rx Market Pulse&apos;s index, where 100 is the year before entry; only quarters 4 and 8 are exported.
      </p>
      <Tip tip={tip} width={width} />
    </div>
  );
}

// ------------------------------------------------------------------------------------------ two sources

export type SourceRow = { label: string; nadac: number; medicaid: number; note?: string };

export function SourceBars({ rows }: { rows: SourceRow[] }) {
  const [wrap, width] = useWidth<HTMLDivElement>(700);
  const labelW = width < 520 ? 92 : 150;
  const m = { top: 8, right: 70, bottom: 8, left: labelW };
  const rowH = 58;
  const h = m.top + m.bottom + rows.length * rowH;
  const iw = width - m.left - m.right;
  const maxAbs = Math.max(...rows.flatMap((r) => [Math.abs(r.nadac), Math.abs(r.medicaid)]), 1);
  const hasNeg = rows.some((r) => r.nadac < 0 || r.medicaid < 0);
  const x = scaleLinear().domain(hasNeg ? [-maxAbs, maxAbs] : [0, maxAbs]).range([0, iw]);
  const zero = x(0);
  return (
    <div ref={wrap}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label="NADAC and Medicaid price effect by segment, side by side">
        <g transform={`translate(${m.left},${m.top})`}>
          <line className="base" x1={zero} x2={zero} y1={0} y2={rows.length * rowH} />
          {rows.map((r, i) => {
            const y0 = i * rowH;
            const bar = (v: number, yy: number, cls: string) => {
              const w = Math.abs(x(v) - zero);
              const xx = v >= 0 ? zero : zero - w;
              return (
                <g>
                  <rect className={cls} x={xx} y={yy} width={Math.max(w, 1)} height={16} rx={2} />
                  <text className="t-strong" x={v >= 0 ? xx + w + 6 : xx - 6} y={yy + 12} textAnchor={v >= 0 ? "start" : "end"}>
                    {signedUsd(v, 2)}
                  </text>
                </g>
              );
            };
            return (
              <g key={r.label}>
                <text className="t-strong" x={-10} y={y0 + 26} textAnchor="end">
                  {r.label}
                </text>
                {bar(r.nadac, y0 + 8, "bar-i")}
                {bar(r.medicaid, y0 + 28, "bar-m")}
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ Januvia and generic sitagliptin

export function SitagliptinChart({ merck, coreEnd, stepDate }: { merck: Merck; coreEnd: string; stepDate: string }) {
  const [wrap, width] = useWidth<HTMLDivElement>(900);
  const host = useRef<HTMLDivElement | null>(null);
  const { tip, atPointer, hide } = useTip(host);
  const narrow = width < 640;
  const m = { top: 20, right: narrow ? 8 : 12, bottom: 36, left: 34 };
  const h = narrow ? 280 : 330;
  const iw = width - m.left - m.right;
  const ih = h - m.top - m.bottom;
  const w = merck.sitagliptinWeekly;
  const t0 = isoToMs(w[0].d);
  const t1 = Date.UTC(2026, 11, 31);
  const x = scaleLinear().domain([t0, t1]).range([0, iw]);
  const y = scaleLinear().domain([0, 20]).range([ih, 0]);
  // step-after: a rate holds until the next weekly file
  const stepPath = (key: "januvia" | "generic", only?: (d: string) => boolean) => {
    const pts = w.filter((r) => r[key] != null && (!only || only(r.d)));
    let d = "";
    pts.forEach((r, i) => {
      const px = x(isoToMs(r.d));
      const py = y(r[key] as number);
      d += i === 0 ? `M${px.toFixed(1)},${py.toFixed(1)}` : ` H${px.toFixed(1)} V${py.toFixed(1)}`;
    });
    const last = pts[pts.length - 1];
    if (last) d += ` H${x(isoToMs(last.d)).toFixed(1)}`;
    return d;
  };
  // the January 2025 step as its own short path so denim covers only the cut
  const stepIdx = w.findIndex((r) => r.d >= stepDate);
  const before = stepIdx > 0 ? w[stepIdx - 1] : null;
  const after = stepIdx >= 0 ? w[stepIdx] : null;
  const cut =
    before?.januvia != null && after?.januvia != null
      ? `M${x(isoToMs(before.d)).toFixed(1)},${y(before.januvia).toFixed(1)} H${x(isoToMs(after.d)).toFixed(1)} V${y(after.januvia).toFixed(1)}`
      : "";
  const years = [2024, 2025, 2026];
  const lastRow = w[w.length - 1];
  const genFirst = w.find((r) => r.generic != null);
  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = host.current?.getBoundingClientRect();
    if (!r) return;
    const t = x.invert(e.clientX - r.left - m.left);
    let best = w[0];
    for (const row of w) if (Math.abs(isoToMs(row.d) - t) < Math.abs(isoToMs(best.d) - t)) best = row;
    atPointer(shortDate(best.d), [
      { label: "Januvia 100 mg", value: rate(best.januvia) },
      { label: "Generic sitagliptin 100 mg", value: best.generic == null ? "not priced" : rate(best.generic) },
    ])(e);
  };
  return (
    <div ref={host} style={{ position: "relative" }}>
      <div ref={wrap}>
        <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={`Weekly NADAC rate for one 100 mg tablet. Januvia fell from ${rate(w[0].januvia)} to ${rate(lastRow.januvia)} on ${longDate(stepDate)}. Generic sitagliptin has been priced since ${genFirst ? longDate(genFirst.d) : "n/a"} at ${rate(lastRow.generic)}.`}>
          <g transform={`translate(${m.left},${m.top})`}>
            {[0, 5, 10, 15, 20].map((t) => (
              <g key={t}>
                <line className="grid" x1={0} x2={iw} y1={y(t)} y2={y(t)} />
                <text className="t-mute" x={-8} y={y(t) + 4} textAnchor="end">
                  ${t}
                </text>
              </g>
            ))}
            {years.map((yr) => (
              <g key={yr}>
                <line className="jan-rule" x1={x(Date.UTC(yr, 0, 1))} x2={x(Date.UTC(yr, 0, 1))} y1={0} y2={ih + 8} />
                <text className="t-mute" x={x(Date.UTC(yr, 0, 1)) + 5} y={ih + 26}>
                  {yr}
                </text>
              </g>
            ))}
            <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            <line className="base" x1={x(isoToMs(coreEnd))} x2={x(isoToMs(coreEnd))} y1={0} y2={ih} strokeDasharray="4 3" />
            <text className="t-strong" x={x(isoToMs(coreEnd)) - 6} y={12} textAnchor="end">
              {narrow ? "Core protection ends" : `Core protection ends ${longDate(coreEnd)} (Orange Book)`}
            </text>
            <path className="l-ink" d={stepPath("januvia")} />
            {cut && <path className="l-denim" d={cut} />}
            <path className="l-mute" d={stepPath("generic")} />
            {lastRow.januvia != null && (
              <text className="t-strong" x={x(isoToMs(lastRow.d)) - 8} y={y(lastRow.januvia) - 10} textAnchor="end">
                Januvia {rate(lastRow.januvia)}
              </text>
            )}
            {lastRow.generic != null && (
              <text className="t-lab" x={x(isoToMs(lastRow.d)) - 8} y={y(lastRow.generic) + 20} textAnchor="end">
                Generic sitagliptin {rate(lastRow.generic)}
              </text>
            )}
            {before?.januvia != null && !narrow && (
              <text className="t-denim" x={x(isoToMs(after!.d)) + 8} y={y((before.januvia + (after!.januvia as number)) / 2)}>
                {rate(before.januvia)} to {rate(after!.januvia)}
              </text>
            )}
            <rect x={0} y={0} width={iw} height={ih} fill="transparent" onPointerMove={onMove} onPointerLeave={hide} />
          </g>
        </svg>
      </div>
      <Tip tip={tip} width={width} />
    </div>
  );
}

// ------------------------------------------------------------------------------------------ weekly grid

export function WeekGrid({ years, cells, cols }: { years: number[]; cells: Cell[]; cols: number }) {
  const [wrap, width] = useWidth<HTMLDivElement>(900);
  const host = useRef<HTMLDivElement | null>(null);
  const { tip, atElement, hide } = useTip(host);
  const left = 40;
  const pitch = (width - left) / cols;
  const size = Math.max(4, Math.min(16, pitch - 2));
  const rowH = Math.max(size + 3, 12);
  const h = years.length * rowH + 24;
  const byYear = new Map(years.map((yr, i) => [yr, i]));
  const bulkCount = cells.filter((c) => c.bulk).length;
  return (
    <div ref={host} style={{ position: "relative" }}>
      <div ref={wrap}>
        <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={`One square for each weekly file, ${years[0]} to ${years[years.length - 1]}. ${bulkCount} of them are monthly bulk updates with more than 1,000 changes.`}>
          {years.map((yr, i) => (
            <text key={yr} className="t-mute" x={0} y={i * rowH + size - 1}>
              {yr}
            </text>
          ))}
          {cells.map((c) => {
            const i = byYear.get(c.y) as number;
            const cls = c.janBulk ? "mk-d" : c.bulk ? "mk-i" : "";
            return (
              <rect
                key={c.d}
                className={cls}
                fill={cls ? undefined : "none"}
                stroke={cls ? undefined : "var(--mute)"}
                strokeWidth={cls ? undefined : 1}
                x={left + c.col * pitch + (cls ? 0 : 0.5)}
                y={i * rowH + (cls ? 0 : 0.5)}
                width={cls ? size : size - 1}
                height={cls ? size : size - 1}
                rx={1}
                onPointerEnter={atElement(shortDate(c.d), [{ label: "Changes", value: int(c.n) }])}
                onPointerLeave={hide}
              />
            );
          })}
          {[1, 14, 27, 40].map((wk) => (
            <text key={wk} className="t-mute" x={left + (wk - 1) * pitch} y={years.length * rowH + 16}>
              week {wk}
            </text>
          ))}
        </svg>
      </div>
      <Tip tip={tip} width={width} />
    </div>
  );
}

export function Glyph({ status }: { status: "pass" | "warn" | "fail" | "info" }) {
  const common = { width: 14, height: 14, viewBox: "0 0 14 14", "aria-hidden": true } as const;
  if (status === "pass")
    return (
      <svg {...common}>
        <path d="M2 7.5 L5.5 11 L12 3" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    );
  if (status === "warn")
    return (
      <svg {...common}>
        <path d="M2 7 H12" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    );
  if (status === "fail")
    return (
      <svg {...common}>
        <path d="M3 3 L11 11 M11 3 L3 11" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    );
  return (
    <svg {...common}>
      <circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

