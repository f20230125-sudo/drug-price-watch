import { describe, expect, it } from "vitest";
import { changeJump, groups, indexTicks, isoToMs, januaryMultiple, januaryShareOfGain, latest, lineSegments, pair, periods, risesPerYear, seasonBars, weekGrid, ymToMs } from "./derive";
import { realDataset } from "./fixtures";

describe("lineSegments", () => {
  const months = ["2024-11", "2024-12", "2025-01", "2025-02", "2025-03", "2025-04"];
  const vals = [100, 100, 110, 112, 112, 112];
  const weeks = [4, 5, 4, 4, 4, 2];
  it("flags the December-to-January and January-to-February segments only", () => {
    const segs = lineSegments(months, vals, weeks, "2024-11");
    expect(segs.map((s) => s.jan)).toEqual([false, true, true, false, false]);
  });
  it("marks only the newest month as partial, and only when it holds under four weeks", () => {
    const segs = lineSegments(months, vals, weeks, "2024-11");
    expect(segs.map((s) => s.partial)).toEqual([false, false, false, false, true]);
  });
  it("starts at the given month and skips gaps", () => {
    const segs = lineSegments(months, [null, 100, 110, null, 112, 112], weeks, "2024-12");
    // 2024-12 to 2025-01 (100 to 110) and 2025-03 to 2025-04 (112 to 112); the two segments touching the gap are skipped
    expect(segs.map((s) => [s.v0, s.v1])).toEqual([[100, 110], [112, 112]]);
  });
  it("splits a gain into the part inside the windows", () => {
    const g = januaryShareOfGain(lineSegments(months, vals, weeks, "2024-11"));
    expect(g.gain).toBe(12);
    expect(g.inWindows).toBe(12);
  });
});

describe("time helpers", () => {
  it("convert a month and a day to milliseconds", () => {
    expect(ymToMs("2026-01")).toBe(Date.UTC(2026, 0, 1));
    expect(isoToMs("2026-09-23")).toBe(Date.UTC(2026, 8, 23));
  });
  it("round ticks outwards to the step", () => {
    expect(indexTicks(40, 130, 25)).toEqual([50, 75, 100, 125]);
  });
  it("find the newest value", () => {
    expect(latest([1, 2, null])).toEqual({ i: 1, v: 2 });
    expect(latest([null, null])).toBeNull();
  });
});

describe("on the real data", () => {
  const d = realDataset();
  it("nearly all of the brand line's gain since 2019 comes in the December to February windows", () => {
    const segs = lineSegments(d.index.months, d.index.series["segment:Brand"].weighted, d.index.weeksInMonth, "2019-01");
    const g = januaryShareOfGain(segs);
    expect(g.gain).toBeGreaterThan(15);
    expect(g.inWindows / g.gain).toBeGreaterThan(0.85);
  });
  it("brand sits above 100 and generic below at the newest month", () => {
    const brand = latest(d.index.series["segment:Brand"].weighted)!.v;
    const generic = latest(d.index.series["segment:Generic"].weighted)!.v;
    expect(brand).toBeCloseTo(d.headline.index.weighted.brand, 1);
    expect(generic).toBeCloseTo(d.headline.index.weighted.generic, 1);
  });
  it("the last month holds fewer than four weeks, so its segment is drawn dashed", () => {
    const segs = lineSegments(d.index.months, d.index.series["segment:Brand"].weighted, d.index.weeksInMonth, "2019-01");
    expect(segs[segs.length - 1].partial).toBe(true);
  });
  it("groups start with the price classes and then list the areas", () => {
    const g = groups(d.index);
    expect(g.slice(0, 3).map((x) => x.label)).toEqual(["All packs", "Brand", "Generic"]);
    expect(g.filter((x) => x.kind === "area").length).toBeGreaterThanOrEqual(10);
  });
  it("January is the tallest calendar bar and shares add up to one", () => {
    const bars = seasonBars(d.events);
    expect(bars.reduce((s, b) => s + b.share, 0)).toBeCloseTo(1, 10);
    expect([...bars].sort((a, b) => b.n - a.n)[0].m).toBe(1);
    expect(januaryMultiple(bars)).toBeGreaterThan(5);
    expect(bars.find((b) => b.m === 1)!.share).toBeCloseTo(d.headline.seasonality.january, 3);
  });
  it("rises per year mark the first and the newest year as part years", () => {
    const yrs = risesPerYear(d.events, 2026);
    expect(yrs.filter((y) => y.partial).map((y) => y.y)).toEqual([2013, 2026]);
  });
  it("brand changes jump between 2023 and 2024", () => {
    const j = changeJump(d.events);
    expect(j.to).toBeGreaterThan(4 * j.from);
  });
  it("the weekly grid has one cell per weekly file and fills the bulk updates", () => {
    const g = weekGrid(d.events);
    expect(g.cells).toHaveLength(d.events.weeks.length);
    expect(g.years[0]).toBe(2014);
    const perYear = g.years.slice(1, -1).map((y) => g.cells.filter((c) => c.y === y && c.bulk).length);
    expect(Math.min(...perYear)).toBeGreaterThanOrEqual(11);
    expect(Math.max(...perYear)).toBeLessThanOrEqual(13);
    expect(g.cells.every((c) => c.col >= 0 && c.col <= 52)).toBe(true);
  });
  it("the two-source pairs cover brand, generic and all for every period", () => {
    for (const p of periods(d.triangulation)) for (const seg of ["Brand", "Generic", "All"]) expect(pair(d.triangulation, p.y0, p.y1, seg).packs).toBeGreaterThan(0);
  });
  it("headline numbers equal the numbers in the series they summarise", () => {
    expect(d.headline.latest.date).toBe(d.movers.latestUpdate);
    expect(d.headline.erosion.brandPriceQ8).toBe(d.erosion.cohort.brand.find((b) => b.k === 8)!.median);
  });
});
