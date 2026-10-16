import { describe, expect, it } from "vitest";
import { count, idx, int, longDate, monthLong, pct, rate, shortDate, signedIndexPct, signedPct, signedUsd, upDown, usd } from "./format";

const MINUS = "−";

describe("money and counts", () => {
  it("compacts dollars with a true minus", () => {
    expect(usd(2_844_075_312, 2)).toBe("$2.84B");
    expect(usd(-1_350_000_000)).toBe(`${MINUS}$1.4B`);
    expect(signedUsd(674_000_000, 0)).toBe("+$674M");
    expect(signedUsd(-1_880_000_000, 2)).toBe(`${MINUS}$1.88B`);
    expect(usd(null)).toBe("n/a");
  });
  it("formats counts", () => {
    expect(count(5300)).toBe("5.3K");
    expect(int(17_317_268)).toBe("17,317,268");
  });
});

describe("rates keep different prices different", () => {
  it("prints three decimals for a tablet and four for a cheap liquid", () => {
    expect(rate(18.334)).toBe("$18.334");
    expect(rate(10.5518)).toBe("$10.552");
    expect(rate(0.0544)).toBe("$0.0544");
    expect(rate(3.7708)).toBe("$3.771");
  });
  it("keeps cents above $100 and whole dollars above $1,000", () => {
    expect(rate(431.2345)).toBe("$431.23");
    expect(rate(21525.549)).toBe("$21,526");
  });
  it("handles a missing rate", () => {
    expect(rate(null)).toBe("n/a");
  });
});

describe("index words", () => {
  it("says up and down against 100", () => {
    expect(upDown(121.96)).toBe("up 22%");
    expect(upDown(46.64)).toBe("down 53%");
    expect(signedIndexPct(121.96)).toBe("+22%");
    expect(signedIndexPct(46.64)).toBe(`${MINUS}53%`);
    expect(idx(121.96)).toBe("122.0");
  });
});

describe("percent and dates", () => {
  it("formats shares and signed changes", () => {
    expect(pct(0.4427)).toBe("44%");
    expect(signedPct(-0.4241)).toBe(`${MINUS}42%`);
    expect(signedPct(0.0243, 1)).toBe("+2.4%");
  });
  it("writes dates in words", () => {
    expect(longDate("2026-09-23")).toBe("23 September 2026");
    expect(shortDate("2026-09-23")).toBe("23 Sep 2026");
    expect(monthLong("2025-01")).toBe("January 2025");
  });
});
