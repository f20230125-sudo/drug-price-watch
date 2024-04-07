import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SECTIONS = ["index", "january", "erosion", "merck", "sources", "movers", "quality", "method"];
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const running = (page: Page) => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length);
const violations = async (page: Page) =>
  (await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`,
  );

test.describe("the report", () => {
  test("loads with its title, one h1 and the eight sections", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto("/");
    await expect(page).toHaveTitle(/Drug Price Watch/);
    await expect(page.locator("h1")).toHaveCount(1);
    for (const id of SECTIONS) await expect(page.locator(`#${id}`)).toHaveCount(1);
    await expect(page.locator("main")).toHaveCount(1);
    await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("the headline states the finding and the first chart draws two lines and January windows", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("Brand prices are up 22% since 2019");
    const first = page.locator("#first-chart");
    await expect(first.locator("path.l-ink").first()).toBeVisible();
    await expect(first.locator("path.l-mute:not(.dashed)")).toHaveCount(1);
    await expect(first.locator("path.dashed")).toHaveCount(2); // the part month, drawn dashed, on each line
    await expect(first.locator("path.l-denim")).toHaveCount(1);
    expect(await first.locator(".t-fig").allTextContents()).toEqual(["122", "47"]);
  });

  test("the first chart can be read by keyboard, month by month", async ({ page }) => {
    await page.goto("/");
    const hit = page.locator("#first-chart .plot-hit");
    await hit.focus();
    await expect(page.locator("#first-chart .tip")).toContainText("Brand");
    const before = await page.locator("#first-chart .tip b").textContent();
    await page.keyboard.press("ArrowLeft");
    await expect(page.locator("#first-chart .tip b")).not.toHaveText(before ?? "");
  });

  test("every Chart and Table switch works", async ({ page }) => {
    await page.goto("/");
    const figures = page.locator("figure.fig:has(.seg)");
    const n = await figures.count();
    expect(n).toBeGreaterThanOrEqual(8);
    for (let i = 0; i < n; i++) {
      const fig = figures.nth(i);
      await fig.scrollIntoViewIfNeeded();
      await fig.getByRole("button", { name: "Table" }).click();
      await expect(fig.locator("table.tbl").first()).toBeVisible();
      await fig.getByRole("button", { name: "Chart" }).click();
      await expect(fig.locator("table.tbl")).toHaveCount(0);
    }
  });

  test("choosing a group in the Index section changes the chart, and the two bases never share an axis", async ({ page }) => {
    await page.goto("/");
    const fig = page.locator("#index figure.fig");
    await expect(fig.locator("h3")).toContainText("since January 2019, brand");
    await page.getByRole("radio", { name: /^Generic/ }).click();
    await expect(fig.locator("h3")).toContainText("generic");
    await page.getByRole("button", { name: /Each pack counts once/ }).click();
    await expect(fig.locator("h3")).toContainText("since December 2013");
    await expect(fig.locator(".sub")).toContainText("December 2013 = 100");
    await page.getByRole("button", { name: /Weighted, from January 2019/ }).click();
    await expect(fig.locator(".sub")).toContainText("January 2019 = 100");
  });

  test("the January section shows January as the tallest bar", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#january h2")).toContainText("44% of brand price rises");
    await expect(page.locator("#january .bar-d")).toHaveCount(1);
  });

  test("the erosion table opens to all 48 molecules", async ({ page }) => {
    await page.goto("/");
    const wrap = page.locator("#erosion .tbl-wrap");
    await expect(wrap.locator("tbody tr")).toHaveCount(12);
    await page.getByRole("button", { name: /Show all 48 molecules/ }).click();
    await expect(wrap.locator("tbody tr")).toHaveCount(48);
  });

  test("the Merck section reports the 28 generic sitagliptin packs", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#merck h2")).toContainText("28 generic sitagliptin packs");
    await expect(page.locator("#merck")).toContainText("Not priced by NADAC");
    await expect(page.locator("#merck")).toContainText("28 generic sitagliptin packs priced");
  });

  test("the two-source period control changes the bars", async ({ page }) => {
    await page.goto("/");
    const fig = page.locator("#sources figure.fig");
    await expect(fig.locator("h3")).toContainText("2022");
    await fig.getByRole("button", { name: /2019.22/ }).click();
    await expect(fig.locator("h3")).toContainText("2019");
  });

  test("the movers list switches between years", async ({ page }) => {
    await page.goto("/");
    const rows = page.locator("#movers .tbl-wrap tbody tr");
    await expect(rows).toHaveCount(15);
    await page.getByRole("button", { name: /Largest in 2025/ }).click();
    await expect(rows).toHaveCount(15);
    await expect(page.getByRole("button", { name: /Largest in 2025/ })).toHaveAttribute("aria-pressed", "true");
  });

  test("the scorecard lists every check with its status in words", async ({ page }) => {
    await page.goto("/");
    expect(await page.locator("#quality .qrow").count()).toBeGreaterThanOrEqual(20);
    await expect(page.locator("#quality .qrow .st", { hasText: "Pass" }).first()).toBeVisible();
  });

  test("the Excel model downloads", async ({ request, page }) => {
    await page.goto("/");
    await expect(page.locator('a[download][href$=".xlsx"]').first()).toBeVisible();
    const res = await request.get("/downloads/Price-Tracker.xlsx");
    expect(res.status()).toBe(200);
    expect((await res.body()).length).toBeGreaterThan(100_000);
  });

  test("theme choice is applied and remembered", async ({ page }) => {
    await page.goto("/");
    await page.locator("button.theme").click();
    const first = await page.locator("html").getAttribute("data-theme");
    expect(["light", "dark"]).toContain(first);
    expect(await page.evaluate(() => localStorage.getItem("pw-theme"))).toBe(first);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", first!);
  });

  test("the share image and icon exist", async ({ request }) => {
    expect((await request.get("/opengraph-image.png")).status()).toBe(200);
    expect((await request.get("/icon.svg")).status()).toBe(200);
  });

  test("an unknown address shows the not-found page", async ({ page }) => {
    const res = await page.goto("/nothing-here");
    expect(res?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "That page does not exist" })).toBeVisible();
  });
});

test.describe("accessibility", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`axe finds no violations on the desktop page (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/");
      expect(await violations(page)).toEqual([]);
    });
    test(`axe finds no violations on a phone (${scheme})`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/");
      expect(await violations(page)).toEqual([]);
    });
  }

  test("with every table open there are still no violations", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    for (const group of await page.locator(".seg").all()) await group.getByRole("button", { name: "Table" }).click();
    expect(await violations(page)).toEqual([]);
  });
});

test.describe("phone", () => {
  for (const width of [390, 360, 320]) {
    test.describe(`${width} px wide`, () => {
      test.use({ viewport: { width, height: 800 } });
      test("no sideways scroll, with the charts and then with every table open", async ({ page }) => {
        await page.goto("/");
        const wide = () => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(await wide()).toBeLessThanOrEqual(1);
        for (const group of await page.locator(".seg").all()) await group.getByRole("button", { name: "Table" }).click();
        expect(await wide()).toBeLessThanOrEqual(1);
      });
    });
  }
  test.describe("menu", () => {
    test.use({ viewport: { width: 390, height: 844 } });
    test("the section menu opens and goes to a section", async ({ page }) => {
      await page.goto("/");
      await page.locator(".sections-menu summary").click();
      await page.locator(".sections-menu .menu a", { hasText: "Merck" }).click();
      await expect(page).toHaveURL(/#merck$/);
    });
    test("a group is chosen from a select on a phone", async ({ page }) => {
      await page.goto("/");
      await page.locator("#grp").selectOption({ label: "Generic" });
      await expect(page.locator("#index figure.fig h3")).toContainText("generic");
    });
  });
});

test.describe("motion", () => {
  test("with reduced motion nothing is animating and the January windows are denim at first paint", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(300);
    expect(await running(page)).toBe(0);
    const stroke = await page.locator("#first-chart path.l-denim").evaluate((el) => getComputedStyle(el).stroke);
    expect(stroke).toBe("rgb(22, 103, 162)");
  });
  test.describe("with motion allowed", () => {
    test.use({ reducedMotion: "no-preference" });
    test("the line is uncovered a year at a time, then the January windows turn denim, and it stops", async ({ page }) => {
      await page.goto("/");
      const win = page.locator("#first-chart path.l-denim");
      await page.waitForTimeout(200);
      expect(await running(page)).toBeGreaterThan(0);
      await page.waitForTimeout(2400);
      expect(await win.evaluate((el) => getComputedStyle(el).stroke)).toBe("rgb(22, 103, 162)");
      expect(await running(page)).toBe(0);
    });
  });
});
