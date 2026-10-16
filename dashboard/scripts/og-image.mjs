// Makes the share image (1200x630) from the top of the live page: node scripts/og-image.mjs
import { chromium } from "@playwright/test";
import path from "node:path";

const out = path.join(process.cwd(), "src", "app", "opengraph-image.png");
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1200, height: 630 }, colorScheme: "light", reducedMotion: "reduce" })).newPage();
await page.goto(process.env.BASE_URL ?? "http://127.0.0.1:3080", { waitUntil: "networkidle" });
await page.addStyleTag({ content: ".bar{display:none!important}.kicker{display:none!important}.hero{padding-top:28px!important}" });
await page.evaluate(() => window.scrollTo(0, 0));
await page.screenshot({ path: out });
await browser.close();
console.log("wrote", out);
