import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { realDataset } from "@/lib/fixtures";
import { Report } from "./Report";

describe("the page, rendered from the real data", () => {
  const html = renderToStaticMarkup(<Report data={realDataset()} repoUrl="https://github.com/example/repo" />);
  it("opens with the finding as a number in the headline", () => {
    expect(html).toMatch(/Brand prices are up 22% since 2019, in steps\. Generic prices are down 53%\./);
  });
  it("has the eight sections in order, each with a heading", () => {
    const ids = ["index", "january", "erosion", "merck", "sources", "movers", "quality", "method"];
    let at = 0;
    for (const id of ids) {
      const i = html.indexOf(`id="${id}"`, at);
      expect(i, id).toBeGreaterThan(at);
      at = i;
      expect(html).toContain(`id="${id}-h"`);
    }
  });
  it("offers the Excel model and the code", () => {
    expect(html).toContain('href="/downloads/Price-Tracker.xlsx"');
    expect(html).toContain("https://github.com/example/repo");
  });
  it("says what is true about generic sitagliptin, not what a first draft said", () => {
    expect(html).toContain("28 generic sitagliptin packs");
    expect(html).not.toMatch(/no generic sitagliptin pack is priced/i);
  });
  it("prints no placeholder or broken number anywhere", () => {
    expect(html).not.toMatch(/undefined|NaN|\[object|Infinity/);
  });
  it("uses no em dash", () => {
    expect(html.includes(String.fromCharCode(0x2014))).toBe(false);
  });
});
