import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// The contrast table in DESIGN.md, recomputed from the real CSS, so changing a colour cannot quietly break it.
const css = fs.readFileSync(path.join(process.cwd(), "src", "app", "globals.css"), "utf-8");

function block(selector: RegExp): Record<string, string> {
  const m = css.match(selector);
  expect(m, String(selector)).toBeTruthy();
  const out: Record<string, string> = {};
  for (const [, k, v] of m![1].matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)) out[k] = v;
  return out;
}
const light = block(/:root \{\s*color-scheme: light;([\s\S]*?)\n\}/);
const dark = { ...light, ...block(/:root\[data-theme="dark"\] \{([\s\S]*?)\n\}/) };

const rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const lin = (c: number) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (h: string) => {
  const [r, g, b] = rgb(h).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: string, b: string) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const mix = (a: string, b: string, pctA: number) => {
  const A = rgb(a);
  const B = rgb(b);
  return `#${A.map((v, i) => Math.round((v * pctA + B[i] * (100 - pctA)) / 100).toString(16).padStart(2, "0")).join("")}`;
};

describe.each([
  ["light", light],
  ["dark", dark],
] as const)("contrast, %s theme", (_name, t) => {
  it("text on paper reaches 4.5:1", () => {
    for (const k of ["ink", "ink-2", "ink-3"]) expect(contrast(t[k], t.paper), k).toBeGreaterThanOrEqual(4.5);
  });
  it("text on the raised paper reaches 4.5:1", () => {
    for (const k of ["ink", "ink-2", "ink-3"]) expect(contrast(t[k], t["paper-2"]), k).toBeGreaterThanOrEqual(4.5);
  });
  it("denim works as text on paper, on the raised paper and on its own wash", () => {
    const wash = mix(t.denim, t.paper, 12);
    expect(contrast(t.denim, t.paper)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t.denim, t["paper-2"])).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t.denim, wash), "denim on the January wash").toBeGreaterThanOrEqual(4.5);
    expect(contrast(t.ink, wash), "ink on the January wash").toBeGreaterThanOrEqual(4.5);
  });
  it("marks reach 3:1 on paper and the accent is told apart from the lines it sits on", () => {
    expect(contrast(t.mute, t.paper)).toBeGreaterThanOrEqual(3);
    expect(contrast(t.denim, t.paper)).toBeGreaterThanOrEqual(3);
    expect(contrast(t.denim, t.ink), "denim against the ink line it overlays").toBeGreaterThanOrEqual(1.5);
    expect(contrast(t.denim, t.mute), "denim against the grey line").toBeGreaterThanOrEqual(1.5);
  });
  it("the selected toggle (paper on ink) is readable", () => {
    expect(contrast(t.paper, t.ink)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("the tokens themselves", () => {
  it("share paper, ink and mute with Rx Market Pulse and Trial Pipeline Benchmark", () => {
    expect(light.paper).toBe("#faf8f3");
    expect(light.ink).toBe("#15302c");
    expect(light.mute).toBe("#948e7f");
    expect(dark.paper).toBe("#111817");
    expect(dark.mute).toBe("#5a6a66");
  });
  it("use denim as the one accent", () => {
    expect(light.denim).toBe("#1667a2");
    expect(dark.denim).toBe("#379de6");
  });
  it("define no other site's accent", () => {
    expect(css).not.toMatch(/--(berry|teal|ochre)/);
  });
});
