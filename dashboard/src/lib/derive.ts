import type { Events, IndexData, Triangulation } from "./schema";

// Pure functions that turn the validated data into what the page draws. No React in here, so they can be tested.

export const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** "2026-09" -> milliseconds at 1 September 2026 UTC. */
export function ymToMs(ym: string): number {
  const [y, m] = ym.split("-").map(Number);
  return Date.UTC(y, m - 1, 1);
}

/** "2026-09-23" -> milliseconds at that day, UTC. */
export function isoToMs(iso: string): number {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

const monthOf = (ym: string) => Number(ym.slice(5, 7));

export type Seg = { i: number; t0: number; t1: number; v0: number; v1: number; jan: boolean; partial: boolean };

/**
 * Straight segments between consecutive months that both have a value, from `from` ("2019-01") on.
 * A segment is a January window when it runs from December to January or from January to February: that is where
 * a brand price step lands, because rates move once a month and the monthly average catches the move in that month
 * and the next. The last segment is partial when the newest month holds fewer than four weekly files.
 */
export function lineSegments(months: string[], values: (number | null)[], weeks: number[], from: string): Seg[] {
  const out: Seg[] = [];
  const start = Math.max(0, months.indexOf(from));
  for (let i = start; i < months.length - 1; i++) {
    const a = values[i];
    const b = values[i + 1];
    if (a == null || b == null) continue;
    const m0 = monthOf(months[i]);
    const m1 = monthOf(months[i + 1]);
    out.push({
      i,
      t0: ymToMs(months[i]),
      t1: ymToMs(months[i + 1]),
      v0: a,
      v1: b,
      jan: (m0 === 12 && m1 === 1) || (m0 === 1 && m1 === 2),
      partial: i + 1 === months.length - 1 && weeks[i + 1] < 4,
    });
  }
  return out;
}

/** How much of a line's net rise came inside the December-to-February windows. Computed, never typed. */
export function januaryShareOfGain(segs: Seg[]): { gain: number; inWindows: number } {
  let gain = 0;
  let inWindows = 0;
  for (const s of segs) {
    const d = s.v1 - s.v0;
    gain += d;
    if (s.jan) inWindows += d;
  }
  return { gain, inWindows };
}

// ------------------------------------------------------------------------------------------ the Index section

export type Group = { key: string; label: string; kind: "class" | "area" };

const CLASS_LABELS: Record<string, string> = {
  All: "All packs",
  Brand: "Brand",
  Generic: "Generic",
  "Branded generic": "Branded generic",
  Biologic: "Biologic",
};

/** The groups the Index section can show: the five price classes, then therapeutic areas by weighted change. */
export function groups(index: IndexData): Group[] {
  const keys = Object.keys(index.series);
  const classes = ["All", "Brand", "Generic", "Branded generic", "Biologic"]
    .filter((c) => keys.includes(`segment:${c}`))
    .map((c) => ({ key: `segment:${c}`, label: CLASS_LABELS[c], kind: "class" as const }));
  const last = index.months.length - 1;
  const areas = keys
    .filter((k) => k.startsWith("area:"))
    .map((k) => ({ key: k, label: k.slice(5), kind: "area" as const, v: index.series[k].weighted[last] ?? 0 }))
    .sort((a, b) => a.v - b.v)
    .map(({ key, label, kind }) => ({ key, label, kind }));
  return [...classes, ...areas];
}

/** The newest non-null value of a series and its position. */
export function latest(values: (number | null)[]): { i: number; v: number } | null {
  for (let i = values.length - 1; i >= 0; i--) {
    const v = values[i];
    if (v != null) return { i, v };
  }
  return null;
}

// ------------------------------------------------------------------------------------------ January: the calendar

export type MonthBar = { m: number; name: string; n: number; share: number };

/** Brand price rises of 2% or more by calendar month, with each month's share of all of them. */
export function seasonBars(events: Events): MonthBar[] {
  const total = events.season.reduce((s, x) => s + x.brandUp2, 0);
  return events.season.map((x) => ({ m: x.m, name: MONTH_NAMES[x.m - 1], n: x.brandUp2, share: x.brandUp2 / total }));
}

/** January's count against the average of the other eleven months. */
export function januaryMultiple(bars: MonthBar[]): number {
  const jan = bars.find((b) => b.m === 1)!.n;
  const others = bars.filter((b) => b.m !== 1);
  return jan / (others.reduce((s, b) => s + b.n, 0) / others.length);
}

export type YearBar = { y: number; n: number; partial: boolean };

/** Brand rises of 2% or more per year. 2013 and the newest year hold only part of a year of weekly files. */
export function risesPerYear(events: Events, newestYear: number): YearBar[] {
  return events.years.map((y) => ({ y: y.y, n: y.brand.steps2, partial: y.y === 2013 || y.y === newestYear }));
}

/** Counts of all brand changes, to show the jump when NADAC changed how it publishes. */
export function changeJump(events: Events): { from: number; to: number; fromY: number; toY: number } {
  const by = new Map(events.years.map((y) => [y.y, y.brand.changes] as const));
  return { fromY: 2023, toY: 2024, from: by.get(2023) ?? 0, to: by.get(2024) ?? 0 };
}

// ------------------------------------------------------------------------------------------ Movers: the weekly grid

export type Cell = { y: number; col: number; d: string; n: number; bulk: boolean; janBulk: boolean };

/** One cell per weekly file, in rows by year and columns by week of the year. A bulk update has more than 1,000 changes. */
export function weekGrid(events: Events): { years: number[]; cells: Cell[]; cols: number } {
  const cells: Cell[] = [];
  for (const w of events.weeks) {
    const [y, m] = w.d.split("-").map(Number);
    const doy = Math.floor((isoToMs(w.d) - Date.UTC(y, 0, 1)) / 86_400_000);
    const bulk = w.n > 1000;
    cells.push({ y, col: Math.min(52, Math.floor(doy / 7)), d: w.d, n: w.n, bulk, janBulk: bulk && m === 1 });
  }
  const years = [...new Set(cells.map((c) => c.y))].sort((a, b) => a - b);
  return { years, cells, cols: 53 };
}

// ------------------------------------------------------------------------------------------ Two sources

export type Period = { y0: number; y1: number; label: string };

export function periods(tri: Triangulation): Period[] {
  const seen = new Set<string>();
  const out: Period[] = [];
  for (const p of tri.pairs) {
    const k = `${p.y0}-${p.y1}`;
    if (!seen.has(k)) {
      seen.add(k);
      out.push({ y0: p.y0, y1: p.y1, label: `${p.y0}–${String(p.y1).slice(2)}` });
    }
  }
  return out;
}

export function pair(tri: Triangulation, y0: number, y1: number, segment: string) {
  const p = tri.pairs.find((x) => x.y0 === y0 && x.y1 === y1 && x.segment === segment);
  if (!p) throw new Error(`no triangulation row for ${segment} ${y0}-${y1}`);
  return p;
}

// ------------------------------------------------------------------------------------------ small helpers

/** Clean axis ticks for an index chart: multiples of 25 that cover [lo, hi]. */
export function indexTicks(lo: number, hi: number, step = 25): number[] {
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(v);
  return out;
}
