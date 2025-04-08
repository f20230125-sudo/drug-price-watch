"use client";

import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { scaleLinear } from "d3-scale";
import { MONTH_NAMES, lineSegments, ymToMs } from "@/lib/derive";
import { idx } from "@/lib/format";
import { Tip, useTip, useWidth } from "./chart";

export type CalLine = {
  key: string;
  label: string;
  values: (number | null)[];
  tone: "ink" | "mute" | "ink3";
  /** Draw the December-to-February windows over the line in denim (a January step). */
  jan?: boolean;
  /** Direct label at the line end. */
  end?: { fig: string; text: string };
};

type Props = {
  months: string[];
  weeks: number[];
  lines: CalLine[];
  from: string;
  /** Calendar years the x axis covers: [2019, 2027] is 1 January 2019 to 1 January 2027. */
  years: [number, number];
  yDomain: [number, number];
  yTicks: number[];
  baseLine?: number;
  height?: number;
  first?: boolean;
  label: string;
};

const toneClass = { ink: "l-ink", mute: "l-mute", ink3: "l-ink3" } as const;

/**
 * A time chart ruled by the calendar: a hairline at every 1 January with the year beside it, a tick for every month
 * and a longer one for July. Lines run straight between monthly values (the data steps; nothing is smoothed). Pointer or
 * arrow keys read a month.
 */
export function CalendarChart({ months, weeks, lines, from, years, yDomain, yTicks, baseLine, height = 330, first = false, label }: Props) {
  const [wrapRef, width] = useWidth<HTMLDivElement>(900);
  const host = useRef<HTMLDivElement | null>(null);
  const { tip, atPointer, hide } = useTip(host);
  const [cursor, setCursor] = useState<number | null>(null);

  const narrow = width < 640;
  const m = { top: 14, right: narrow ? 74 : 230, bottom: 38, left: 34 };
  const h = narrow ? Math.round(height * 0.8) : height;
  const iw = Math.max(120, width - m.left - m.right);
  const ih = h - m.top - m.bottom;
  const t0 = Date.UTC(years[0], 0, 1);
  const t1 = Date.UTC(years[1], 0, 1);
  const x = scaleLinear().domain([t0, t1]).range([0, iw]);
  const y = scaleLinear().domain(yDomain).range([ih, 0]);
  const yearList = Array.from({ length: years[1] - years[0] }, (_, i) => years[0] + i);
  const first0 = Math.max(0, months.indexOf(from));

  const monthTicks: { t: number; july: boolean }[] = [];
  for (let yr = years[0]; yr < years[1]; yr++) for (let mo = 0; mo < 12; mo++) monthTicks.push({ t: Date.UTC(yr, mo, 1), july: mo === 6 });

  const indexAt = (px: number): number => {
    const t = x.invert(px - m.left);
    let best = first0;
    let bd = Infinity;
    for (let i = first0; i < months.length; i++) {
      const d = Math.abs(ymToMs(months[i]) - t);
      if (d < bd) {
        bd = d;
        best = i;
      }
    }
    return best;
  };

  const show = (i: number, ev?: { clientX: number; clientY: number }) => {
    setCursor(i);
    const [yr, mo] = months[i].split("-").map(Number);
    const rows = lines.map((l) => ({ label: l.label, value: l.values[i] == null ? "n/a" : idx(l.values[i]) }));
    const lead = lines[0].values;
    if (i > first0 && lead[i] != null && lead[i - 1] != null) {
      const d = (lead[i] as number) - (lead[i - 1] as number);
      rows.push({ label: `${lines[0].label} on the month`, value: `${d < 0 ? "−" : "+"}${Math.abs(d).toFixed(1)}` });
    }
    const title = `${MONTH_NAMES[mo - 1]} ${yr}${weeks[i] < 4 ? ` (${weeks[i]} weeks)` : ""}`;
    if (ev) atPointer(title, rows)(ev);
    else {
      const px = m.left + x(ymToMs(months[i]));
      const py = m.top + y((lead[i] ?? yDomain[0]) as number);
      atPointer(title, rows)({ clientX: (host.current?.getBoundingClientRect().left ?? 0) + px, clientY: (host.current?.getBoundingClientRect().top ?? 0) + py });
    }
  };

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = host.current?.getBoundingClientRect();
    if (!r) return;
    show(indexAt(e.clientX - r.left), e);
  };
  const onKey = (e: KeyboardEvent<SVGRectElement>) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const cur = cursor ?? months.length - 1;
    show(Math.min(months.length - 1, Math.max(first0, cur + step)));
  };
  const leave = () => {
    hide();
    setCursor(null);
  };

  const geometry = lines.map((l) => {
    const segs = lineSegments(months, l.values, weeks, from);
    const solid = segs.filter((s) => !s.partial);
    const partial = segs.filter((s) => s.partial);
    const pts = (ss: typeof segs) => ss.map((s) => [[x(s.t0), y(s.v0)], [x(s.t1), y(s.v1)]] as [number, number][]);
    const runs = (ss: typeof segs): string => {
      let d = "";
      let last: [number, number] | null = null;
      for (const [a, b] of pts(ss)) {
        if (!last || Math.abs(last[0] - a[0]) > 0.5 || Math.abs(last[1] - a[1]) > 0.5) d += `M${a[0].toFixed(1)},${a[1].toFixed(1)} `;
        d += `L${b[0].toFixed(1)},${b[1].toFixed(1)} `;
        last = b;
      }
      return d.trim();
    };
    const lastSeg = segs[segs.length - 1];
    return {
      line: l,
      all: runs(solid),
      jan: l.jan ? runs(solid.filter((s) => s.jan)) : "",
      partial: runs(partial),
      end: lastSeg ? ([x(lastSeg.t1), y(lastSeg.v1)] as [number, number]) : null,
    };
  });

  const cx = cursor == null ? null : x(ymToMs(months[cursor]));

  return (
    <div className={`cal${first ? " first" : ""}`} ref={host}>
      <div className="cal-in" ref={wrapRef}>
        <svg className="svg axes" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="group" aria-label={label}>
          <g transform={`translate(${m.left},${m.top})`}>
            {yTicks.map((t) => (
              <g key={t}>
                <line className={t === baseLine ? "base" : "grid"} x1={0} x2={iw} y1={y(t)} y2={y(t)} />
                <text className="t-mute" x={-8} y={y(t) + 4} textAnchor="end">
                  {t}
                </text>
              </g>
            ))}
            {yearList.map((yr, i) => (
              <g key={yr}>
                <line className="jan-rule" x1={x(Date.UTC(yr, 0, 1))} x2={x(Date.UTC(yr, 0, 1))} y1={0} y2={ih + 8} />
                {(!narrow || i % 2 === 0) && (
                  <text className="t-mute" x={x(Date.UTC(yr, 0, 1)) + 5} y={ih + 26}>
                    {yr}
                  </text>
                )}
              </g>
            ))}
            {monthTicks.map((t) => (
              <line key={t.t} className="tick" x1={x(t.t)} x2={x(t.t)} y1={ih} y2={ih + (t.july ? 8 : 4)} />
            ))}
            <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            <rect
              className="plot-hit"
              x={0}
              y={0}
              width={iw}
              height={ih}
              fill="transparent"
              tabIndex={0}
              role="img"
              aria-label={`${label}. Use the left and right arrow keys to read each month.`}
              onPointerMove={onMove}
              onPointerLeave={leave}
              onFocus={() => show(cursor ?? months.length - 1)}
              onBlur={leave}
              onKeyDown={onKey}
            />
          </g>
        </svg>
        <svg className="svg data" viewBox={`0 0 ${width} ${h}`} width={width} height={h} aria-hidden="true">
          <g transform={`translate(${m.left},${m.top})`}>
            {geometry.map(({ line, all, jan, partial, end }) => (
              <g key={line.key}>
                <path className={toneClass[line.tone]} d={all} />
                {jan && <path className="l-denim jwin" d={jan} />}
                {partial && <path className={`${toneClass[line.tone]} dashed`} d={partial} />}
                {end && (
                  <>
                    <rect className={line.tone === "ink" ? "mk-i" : "mk-m"} x={end[0] - 3.5} y={end[1] - 3.5} width={7} height={7} rx={1} />
                    {line.end && (
                      <g transform={`translate(${end[0] + 14},${end[1]})`}>
                        <text className="t-fig" x={0} y={narrow ? -10 : 10} fontSize={narrow ? 22 : 30}>
                          {line.end.fig}
                        </text>
                        {!narrow && (
                          <text className="t-lab" x={50} y={-4}>
                            <tspan x={50} dy={0}>
                              {line.end.text.split("\n")[0]}
                            </tspan>
                            <tspan x={50} dy={15}>
                              {line.end.text.split("\n")[1] ?? ""}
                            </tspan>
                          </text>
                        )}
                      </g>
                    )}
                  </>
                )}
              </g>
            ))}
            {cx != null && cursor != null && (
              <g>
                <line className="guide" x1={cx} x2={cx} y1={0} y2={ih} />
                {lines.map((l) =>
                  l.values[cursor] == null ? null : (
                    <rect key={l.key} className={l.tone === "ink" ? "mk-i" : "mk-m"} x={cx - 3.5} y={y(l.values[cursor] as number) - 3.5} width={7} height={7} rx={1} />
                  ),
                )}
              </g>
            )}
          </g>
        </svg>
      </div>
      <Tip tip={tip} width={width} />
    </div>
  );
}
