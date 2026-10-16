import fs from "node:fs";
import path from "node:path";
import { Erosion, Events, Headline, IndexData, Merck, Meta, Movers, Quality, Triangulation, Watch, type Dataset } from "./schema";

// The real data files, for tests. (lib/load.ts is server-only and cannot be imported from a test.)
const DIR = path.join(process.cwd(), "public", "data");
const read = <T>(file: string, schema: { parse: (v: unknown) => T }): T => schema.parse(JSON.parse(fs.readFileSync(path.join(DIR, file), "utf-8")));

export function realDataset(): Dataset {
  return {
    headline: read("headline.json", Headline),
    index: read("index.json", IndexData),
    events: read("events.json", Events),
    movers: read("movers.json", Movers),
    erosion: read("erosion.json", Erosion),
    merck: read("merck.json", Merck),
    triangulation: read("triangulation.json", Triangulation),
    quality: read("quality.json", Quality),
    meta: read("meta.json", Meta),
    watch: read("watch.json", Watch),
    workbookKb: 278,
  };
}
