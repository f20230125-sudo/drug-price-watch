import { z } from "zod";

// One schema per file in public/data. The page is built from these, so a field that is missing, renamed or the
// wrong type fails the build with the file name, instead of printing "undefined" on the page.

const num = z.number();
const nums = z.array(z.number().nullable());

export const Headline = z.object({
  asOf: z.string(),
  firstWeek: z.string(),
  weeks: num,
  factRows: num,
  packs: num,
  stagedRows: num,
  latestUpdate: z.string(),
  index: z.object({
    month: z.string(),
    base: z.string(),
    weighted: z.object({ all: num, brand: num, generic: num }),
    equalWeight: z.object({ all: num, brand: num, generic: num }),
  }),
  seasonality: z.object({ brandSteps: num, january: num, july: num, janJul: num }),
  erosion: z.object({
    molecules: num,
    brandPriced: num,
    genericPriced: num,
    brandPriceQ8: num,
    genericPriceQ8: num,
    genericPriceQ12: num,
    brandSpendQ8: num,
    brandSpendQ4: num,
    brandPriceQ4: num,
  }),
  triangulation: z.object({
    y0: num,
    y1: num,
    coverageSpend: num,
    coverageUnits: num,
    rxPriceEffect: num,
    all: z.object({ nadac: num, medicaid: num, corr: num }),
    brand: z.object({ nadac: num, medicaid: num, corr: num, coverageSpend: num }),
  }),
  merck: z.object({
    januvia: z.object({ pack: z.string(), stepDate: z.string(), from: num, to: num, stepPct: num }),
    sitagliptin: z.object({
      genericPacks: num,
      genericLabelers: num,
      genericFirstWeek: z.string(),
      genericRate100: num,
      januviaRate100: num,
      ratio100: num,
    }),
    coreEnd: z.string(),
    brandIndexNow: num,
    priced: num,
    families: num,
  }),
  latest: z.object({ date: z.string(), changes: num, ups: num, downs: num, material: num, medianChange: num }),
  checks: z.object({ pass: num, warn: num, fail: num, info: num, total: num }),
});
export type Headline = z.infer<typeof Headline>;

export const IndexData = z.object({
  months: z.array(z.string()),
  weeksInMonth: z.array(num),
  packsMatched: nums,
  series: z.record(z.string(), z.object({ equal: nums, weighted: nums })),
  weightedFrom: z.string(),
  base: z.object({ weighted: z.string(), equal: z.string() }),
});
export type IndexData = z.infer<typeof IndexData>;

const YearSeg = z.object({
  priced: num,
  changes: num,
  material: num,
  ups: num,
  downs: num,
  materialUps: num,
  materialDowns: num,
  steps2: num,
  medianUp: num.nullable(),
  medianDown: num.nullable(),
  shareOfWeeksChanged: num.nullable(),
});

export const Events = z.object({
  years: z.array(z.object({ y: num, brand: YearSeg, generic: YearSeg })),
  season: z.array(z.object({ m: num, brandUp2: num, brandDown2: num, brandChanges: num })),
  drift: z.array(z.object({ y: num, shareUnderHalfPercent: num.nullable() })),
  bulkUpdates: z.array(z.object({ date: z.string(), changes: num })),
  weeks: z.array(z.object({ d: z.string(), n: num })),
});
export type Events = z.infer<typeof Events>;

const Mover = z.object({
  ndc: z.string(),
  name: z.string(),
  segment: z.string(),
  owner: z.string().nullable(),
  family: z.string().nullable(),
  date: z.string(),
  from: num,
  to: num,
  pct: num,
  units: num.nullable(),
  annualValue: num.nullable(),
});
export const Movers = z.object({
  latestUpdate: z.string(),
  changes: num,
  ups: num,
  downs: num,
  medianChange: num,
  material: num,
  lists: z.record(z.string(), z.array(Mover)),
});
export type Movers = z.infer<typeof Movers>;

const Band = z.object({ k: num, median: num.nullable(), p25: num.nullable(), p75: num.nullable(), events: num });
export const Erosion = z.object({
  cohort: z.object({ brand: z.array(Band), generic: z.array(Band) }),
  events: z.array(
    z.object({
      ingredient: z.string(),
      brand: z.string(),
      entry: z.string().nullable(),
      runRateMusd: num.nullable(),
      brandPriceQ4: num.nullable(),
      brandPriceQ8: num.nullable(),
      genericPriceQ4: num.nullable(),
      genericPriceQ8: num.nullable(),
      brandSpendQ4: num.nullable(),
      brandSpendQ8: num.nullable(),
    }),
  ),
  spendMedian: z.object({ q4: num.nullable(), q8: num.nullable(), eventsQ4: num, eventsQ8: num }),
});
export type Erosion = z.infer<typeof Erosion>;

export const Merck = z.object({
  families: z.array(
    z.object({
      family: z.string(),
      franchise: z.string(),
      area: z.string(),
      spend2025: num,
      status: z.string(),
      coreEnd: z.string().nullable(),
      pack: z.string().nullable(),
      price2019: num.nullable(),
      price2022: num.nullable(),
      price2025: num.nullable(),
      priceLatest: num.nullable(),
      changeSince2019: num.nullable(),
      familyIndex: num.nullable(),
      inNadac: z.boolean(),
    }),
  ),
  brandIndexNow: num,
  sitagliptinWeekly: z.array(z.object({ d: z.string(), januvia: num.nullable(), generic: num.nullable() })),
  sitagliptin: z.object({
    genericPacks: num,
    genericLabelers: num,
    genericFirstWeek: z.string().nullable(),
    brandPacks: num,
    rates: z.array(z.object({ strength: z.string(), genericPacks: num, genericRate: num, januviaRate: num, ratio: num })),
  }),
});
export type Merck = z.infer<typeof Merck>;

export const Triangulation = z.object({
  pairs: z.array(
    z.object({
      y0: num,
      y1: num,
      segment: z.string(),
      packs: num,
      coverageSpend: num,
      coverageUnits: num,
      nadacEffect: num,
      medicaidEffect: num,
      nadacChange: num,
      medicaidChange: num,
      rankCorr: num,
    }),
  ),
  rx: z.array(z.object({ y0: num, y1: num, rxPriceEffect: num, rxSpendChange: num })),
});
export type Triangulation = z.infer<typeof Triangulation>;

export const Quality = z.array(
  z.object({
    id: z.string(),
    dimension: z.string(),
    name: z.string(),
    result: z.string(),
    rule: z.string(),
    status: z.enum(["pass", "warn", "fail", "info"]),
    note: z.string(),
  }),
);
export type Quality = z.infer<typeof Quality>;

export const Meta = z.object({
  built: z.string(),
  sources: z.array(z.object({ name: z.string(), publisher: z.string(), url: z.string() })),
  expectedRows: z.record(z.string(), num),
});
export type Meta = z.infer<typeof Meta>;

export const Watch = z.object({
  checked: z.string(),
  latestWeek: z.string(),
  rows: num,
  packs: num,
  checks: z.array(z.object({ name: z.string(), ok: z.boolean(), value: z.string() })),
  watches: z.array(
    z.object({
      name: z.string(),
      kind: z.string(),
      found: num,
      flag: z.boolean(),
      packs: z.array(z.string()),
      moves: z.array(z.object({ pack: z.string(), from: num, to: num, pct: num })),
    }),
  ),
  flags: z.array(z.string()),
  status: z.string(),
});
export type Watch = z.infer<typeof Watch>;

export type Dataset = {
  headline: Headline;
  index: IndexData;
  events: Events;
  movers: Movers;
  erosion: Erosion;
  merck: Merck;
  triangulation: Triangulation;
  quality: Quality;
  meta: Meta;
  watch: Watch;
  workbookKb: number;
};
