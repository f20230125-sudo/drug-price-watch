import "server-only";
import fs from "node:fs";
import path from "node:path";
import { Erosion, Events, Headline, IndexData, Merck, Meta, Movers, Quality, Triangulation, Watch, type Dataset } from "./schema";

const DIR = path.join(process.cwd(), "public", "data");

function read<T>(file: string, schema: { parse: (v: unknown) => T }): T {
  const raw = JSON.parse(fs.readFileSync(path.join(DIR, file), "utf-8"));
  try {
    return schema.parse(raw);
  } catch (e) {
    throw new Error(`${file} does not match its schema: ${e instanceof Error ? e.message : String(e)}`);
  }
}

/** Reads and validates every data file. Runs at build time on the server; the page ships the result. */
export function loadDataset(): Dataset {
  const xlsx = path.join(process.cwd(), "public", "downloads", "Price-Tracker.xlsx");
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
    workbookKb: Math.round(fs.statSync(xlsx).size / 1000),
  };
}
