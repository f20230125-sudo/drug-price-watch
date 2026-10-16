"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  changeJump,
  groups,
  indexTicks,
  januaryMultiple,
  januaryShareOfGain,
  latest,
  lineSegments,
  pair,
  periods,
  risesPerYear,
  seasonBars,
  weekGrid,
} from "@/lib/derive";
import type { Dataset } from "@/lib/schema";
import { idx, int, longDate, monthLong, pct, rate, shortDate, signedIndexPct, signedPct, signedUsd, upDown, usd } from "@/lib/format";
import { CalendarChart, type CalLine } from "./CalendarChart";
import { ErosionChart, Glyph, SeasonBars, SitagliptinChart, SourceBars, WeekGrid, YearBars } from "./Charts";
import { Fig } from "./Fig";
import { ThemeToggle } from "./ThemeToggle";

const SECTIONS: { id: string; label: string }[] = [
  { id: "index", label: "Index" },
  { id: "january", label: "January" },
  { id: "erosion", label: "Erosion" },
  { id: "merck", label: "Merck" },
  { id: "sources", label: "Two sources" },
  { id: "movers", label: "Movers" },
  { id: "quality", label: "Quality" },
  { id: "method", label: "Method" },
];

function Section({ id, title, dek, children }: { id: string; title: string; dek?: ReactNode; children: ReactNode }) {
  return (
    <section className="sec" id={id} aria-labelledby={`${id}-h`}>
      <div className="sec-head">
        <h2 id={`${id}-h`}>{title}</h2>
        {dek && <p className="dek">{dek}</p>}
      </div>
      <div className="sec-body">{children}</div>
    </section>
  );
}

function Legend({ items }: { items: { cls?: string; label: string }[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label}>
          <i className={i.cls} />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------------------------- first screen

function FirstChart({ d }: { d: Dataset }) {
  const { index, headline: h } = d;
  const brand = index.series["segment:Brand"].weighted;
  const generic = index.series["segment:Generic"].weighted;
  const lines: CalLine[] = [
    { key: "brand", label: "Brand", values: brand, tone: "ink", jan: true, end: { fig: idx(h.index.weighted.brand, 0), text: `Brand, ${upDown(h.index.weighted.brand)}\nsince January 2019` } },
    { key: "generic", label: "Generic", values: generic, tone: "mute", end: { fig: idx(h.index.weighted.generic, 0), text: `Generic, ${upDown(h.index.weighted.generic)}\nsince January 2019` } },
  ];
  const segs = lineSegments(index.months, brand, index.weeksInMonth, "2019-01");
  const gain = januaryShareOfGain(segs);
  return (
    <Fig
      id="first-chart"
      title="Price index since January 2019, brand against generic"
      sub={`Weighted by Medicaid units. January 2019 = 100. Of the ${gain.gain.toFixed(0)} index points the brand line gained, ${gain.inWindows.toFixed(0)} came in the December to February windows.`}
      legend={<Legend items={[{ label: "Brand" }, { cls: "mute", label: "Generic" }, { cls: "denim", label: "January step" }]} />}
      source={
        <>
          Source: CMS NADAC weekly rates, {int(h.factRows)} rows for {int(h.packs)} packs, monthly averages of the weekly index. {monthLong(h.index.month)} holds{" "}
          {index.weeksInMonth[index.weeksInMonth.length - 1]} weeks (dashed).
        </>
      }
      table={<IndexTable months={index.months} cols={[{ label: "Brand", v: brand }, { label: "Generic", v: generic }]} from="2019-01" />}
    >
      <CalendarChart
        first
        months={index.months}
        weeks={index.weeksInMonth}
        lines={lines}
        from="2019-01"
        years={[2019, 2027]}
        yDomain={[40, 130]}
        yTicks={[50, 75, 100, 125]}
        baseLine={100}
        label={`Price index since January 2019. Brand ${idx(h.index.weighted.brand, 0)}, generic ${idx(h.index.weighted.generic, 0)}.`}
      />
    </Fig>
  );
}

function IndexTable({ months, cols, from }: { months: string[]; cols: { label: string; v: (number | null)[] }[]; from: string }) {
  const start = Math.max(0, months.indexOf(from));
  const rows = months.map((m, i) => ({ m, i })).slice(start);
  return (
    <table className="tbl">
      <caption>Monthly average of the weekly index; January rows are shaded.</caption>
      <thead>
        <tr>
          <th scope="col">Month</th>
          {cols.map((c) => (
            <th key={c.label} scope="col" className="n">
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map(({ m, i }) => (
          <tr key={m} className={m.endsWith("-01") ? "hl" : undefined}>
            <th scope="row">{monthLong(m)}</th>
            {cols.map((c) => (
              <td key={c.label} className="n">
                {idx(c.v[i])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------------------------- Index section

function IndexSection({ d }: { d: Dataset }) {
  const [group, setGroup] = useState("segment:Brand");
  const [basis, setBasis] = useState<"weighted" | "equal">("weighted");
  const list = useMemo(() => groups(d.index), [d.index]);
  const cur = list.find((g) => g.key === group) ?? list[0];
  const from = basis === "weighted" ? "2019-01" : d.index.months.find((m, i) => d.index.series["segment:All"].equal[i] != null) ?? "2013-12";
  const fromYear = Number(from.slice(0, 4));
  const val = (key: string) => d.index.series[key][basis];
  const sel = val(cur.key);
  const all = val("segment:All");
  const lines: CalLine[] = [{ key: "sel", label: cur.label, values: sel, tone: "ink", jan: true, end: { fig: idx(latest(sel)?.v ?? null, 0), text: `${cur.label}\n${latest(sel) ? upDown(latest(sel)!.v) : ""}` } }];
  if (cur.key !== "segment:All") lines.push({ key: "all", label: "All packs", values: all, tone: "mute", end: { fig: idx(latest(all)?.v ?? null, 0), text: `All packs\n${latest(all) ? upDown(latest(all)!.v) : ""}` } });
  const seen = lines.flatMap((l) => l.values.slice(Math.max(0, d.index.months.indexOf(from)))).filter((v): v is number => v != null);
  const lo = Math.min(...seen, 100);
  const hi = Math.max(...seen, 100);
  const step = hi - lo > 160 ? 50 : 25;
  const dom: [number, number] = [Math.floor((lo - 8) / step) * step, Math.ceil((hi + 8) / step) * step];
  const base = basis === "weighted" ? "January 2019" : "December 2013";
  const title = basis === "weighted" ? `Price index since January 2019, ${cur.label.toLowerCase()}` : `Price index since December 2013, ${cur.label.toLowerCase()}`;
  const sub = basis === "weighted" ? `Weighted by Medicaid units. ${base} = 100.` : `Every pack counts once, so it reads as the typical pack, not the typical dollar. ${base} = 100.`;
  return (
    <Section id="index" title="The same index for any group of drugs" dek="Five price classes and the therapeutic areas Rx Market Pulse assigns. Two ways to build it, with different starting points: the page never shows them on one axis.">
      <div className="pair">
        <div className="glist-wrap">
          <h4>Group</h4>
          <div className="head" aria-hidden="true">
            <span>Group</span>
            <span className="n">Now</span>
            <span className="n">Change</span>
          </div>
          <div className="glist" role="radiogroup" aria-label="Group of drugs">
            {list.map((g) => {
              const v = latest(val(g.key))?.v ?? null;
              return (
                <button key={g.key} type="button" role="radio" aria-checked={g.key === cur.key} onClick={() => setGroup(g.key)}>
                  <span>{g.label}</span>
                  <span className="n">{idx(v)}</span>
                  <span className="n">{v == null ? "n/a" : signedIndexPct(v)}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div>
          <div className="sel-phone">
            <label className="sr-only" htmlFor="grp">
              Group of drugs
            </label>
            <select id="grp" value={cur.key} onChange={(e) => setGroup(e.target.value)}>
              {list.map((g) => (
                <option key={g.key} value={g.key}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>
          <div className="chips" role="group" aria-label="How the index is built">
            <button type="button" aria-pressed={basis === "weighted"} onClick={() => setBasis("weighted")}>
              Weighted, from January 2019
            </button>
            <button type="button" aria-pressed={basis === "equal"} onClick={() => setBasis("equal")}>
              Each pack counts once, from December 2013
            </button>
          </div>
          <Fig
            key={`${basis}-${cur.key}`}
            title={title}
            sub={sub}
            legend={<Legend items={[{ label: cur.label }, ...(cur.key !== "segment:All" ? [{ cls: "mute", label: "All packs" }] : []), { cls: "denim", label: "January step" }]} />}
            source={<>Source: CMS NADAC weekly rates; {basis === "weighted" ? "Medicaid units from Rx Market Pulse (2019 on)" : "matched packs, equal weights"}.</>}
            table={<IndexTable months={d.index.months} from={from} cols={[{ label: cur.label, v: sel }, ...(cur.key !== "segment:All" ? [{ label: "All packs", v: all }] : [])]} />}
          >
            <CalendarChart months={d.index.months} weeks={d.index.weeksInMonth} lines={lines} from={from} years={[fromYear, 2027]} yDomain={dom} yTicks={indexTicks(dom[0], dom[1], step)} baseLine={100} label={`${title}. ${sub}`} />
          </Fig>
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- January

function JanuarySection({ d }: { d: Dataset }) {
  const bars = seasonBars(d.events);
  const jan = bars.find((b) => b.m === 1)!;
  const jul = bars.find((b) => b.m === 7)!;
  const rank = [...bars].sort((a, b) => b.n - a.n).findIndex((b) => b.m === 7) + 1;
  const mult = januaryMultiple(bars);
  const yrs = risesPerYear(d.events, Number(d.headline.asOf.slice(0, 4)));
  const jump = changeJump(d.events);
  const sh = d.headline.seasonality;
  return (
    <Section id="january" title={`${pct(sh.january)} of brand price rises of 2% or more land in January`} dek={`A rise of 2% or more in one pack's rate, counted by calendar month over ${yrs[1].y} to ${yrs[yrs.length - 2].y}. January holds ${mult.toFixed(1)} times the average of the other eleven months; July is number ${rank}, and January and July together hold ${pct(sh.janJul)} where an even spread would give 17%.`}>
      <Fig
        title="When brand prices rise"
        sub={`${int(sh.brandSteps)} rises of 2% or more, 2014 to 2025, as a share of all of them.`}
        legend={<Legend items={[{ cls: "sq denim", label: "January" }, { cls: "sq", label: "Other months" }]} />}
        source="Source: CMS NADAC weekly rates; a rise is a week in which a brand pack's rate is 2% or more above the week before."
        table={
          <table className="tbl">
            <caption>Brand price rises of 2% or more, by calendar month</caption>
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col" className="n">Rises</th>
                <th scope="col" className="n">Share</th>
              </tr>
            </thead>
            <tbody>
              {bars.map((b) => (
                <tr key={b.m} className={b.m === 1 ? "hl" : undefined}>
                  <th scope="row">{b.name}</th>
                  <td className="n">{int(b.n)}</td>
                  <td className="n">{(b.share * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      >
        <SeasonBars bars={bars} />
      </Fig>
      <div className="pair">
        <Fig
          title="Rises of 2% or more, by year"
          sub="Brand packs. The first and last years hold only part of a year of weekly files."
          legend={<Legend items={[{ cls: "sq", label: "Full year" }, { cls: "hatch", label: "Part year" }]} />}
          source="Source: CMS NADAC weekly rates."
          table={
            <table className="tbl">
              <caption>Brand rises of 2% or more per year</caption>
              <thead>
                <tr>
                  <th scope="col">Year</th>
                  <th scope="col" className="n">Rises</th>
                </tr>
              </thead>
              <tbody>
                {yrs.map((b) => (
                  <tr key={b.y}>
                    <th scope="row">{b.y}{b.partial ? " (part year)" : ""}</th>
                    <td className="n">{int(b.n)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          <YearBars bars={yrs} />
        </Fig>
        <p className="limits">
          <b>Why rises of 2% or more.</b> Counting every change would mislead. From 2024 NADAC&apos;s brand rates start moving by hundredths of a percent at every update, so brand changes go from {int(jump.from)} in {jump.fromY} to {int(jump.to)} in {jump.toY} with no market event behind it (scorecard check C14). January holds {jan.n > 0 ? int(jan.n) : "n/a"} rises, July {int(jul.n)}.
        </p>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- erosion

function ErosionSection({ d }: { d: Dataset }) {
  const e = d.headline.erosion;
  const [all, setAll] = useState(false);
  const rows = all ? d.erosion.events : d.erosion.events.slice(0, 12);
  return (
    <Section id="erosion" title={`After a generic is priced, the brand's unit price holds (${idx(e.brandPriceQ8, 0)}) and its Medicaid spend falls to ${idx(e.brandSpendQ8)}% of its earlier level`} dek={`Median across molecules, measured in quarters from the first quarter generics reach 10% of prescriptions (Rx Market Pulse). ${e.brandPriced} of ${e.molecules} molecules have brand packs NADAC prices; ${e.genericPriced} have generic packs. A median is not a forecast for any one product.`}>
      <Fig
        title="Price and spend after the first generic"
        sub="Brand and generic unit price from NADAC; brand Medicaid spend from Rx Market Pulse."
        legend={<Legend items={[{ label: "Brand price, median" }, { cls: "mute", label: "Generic price, median" }, { cls: "band", label: "Middle half of molecules" }, { cls: "sq ink", label: "Brand Medicaid spend" }]} />}
        source="Source: CMS NADAC weekly rates; Rx Market Pulse (State Drug Utilization Data)."
        table={
          <table className="tbl">
            <caption>Median price index by quarters since the first generic was priced</caption>
            <thead>
              <tr>
                <th scope="col">Quarter</th>
                <th scope="col" className="n">Brand price</th>
                <th scope="col" className="n">Generic price</th>
                <th scope="col" className="n">Brand spend</th>
              </tr>
            </thead>
            <tbody>
              {d.erosion.cohort.brand.map((b) => {
                const g = d.erosion.cohort.generic.find((x) => x.k === b.k);
                const sp = b.k === 4 ? d.erosion.spendMedian.q4 : b.k === 8 ? d.erosion.spendMedian.q8 : null;
                return (
                  <tr key={b.k}>
                    <th scope="row">{b.k}</th>
                    <td className="n">{idx(b.median)}</td>
                    <td className="n">{g ? idx(g.median) : "n/a"}</td>
                    <td className="n">{sp == null ? "n/a" : idx(sp)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        }
      >
        <ErosionChart erosion={d.erosion} spendQ4={d.erosion.spendMedian.q4} spendQ8={d.erosion.spendMedian.q8} molecules={{ brand: e.brandPriced, generic: e.genericPriced }} />
      </Fig>
      <div>
        <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Molecules behind the erosion chart">
          <table className="tbl">
            <caption>{all ? `All ${d.erosion.events.length} molecules` : `The 12 largest of ${d.erosion.events.length} molecules by brand run rate`}; blank where NADAC does not price that side.</caption>
            <thead>
              <tr>
                <th scope="col">Molecule</th>
                <th scope="col">Brand</th>
                <th scope="col">Entry</th>
                <th scope="col" className="n">Brand price, q8</th>
                <th scope="col" className="n">Generic price, q8</th>
                <th scope="col" className="n">Brand spend, q8</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.ingredient}-${r.brand}`}>
                  <th scope="row" className="nm">{r.ingredient.toLowerCase()}</th>
                  <td>{r.brand.toLowerCase()}</td>
                  <td>{r.entry ? monthLong(r.entry.slice(0, 7)) : "n/a"}</td>
                  <td className="n">{r.brandPriceQ8 == null ? "" : idx(r.brandPriceQ8)}</td>
                  <td className="n">{r.genericPriceQ8 == null ? "" : idx(r.genericPriceQ8)}</td>
                  <td className="n">{r.brandSpendQ8 == null ? "" : idx(r.brandSpendQ8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p style={{ margin: "10px 0 0" }}>
          <button type="button" className="btn" onClick={() => setAll((v) => !v)}>
            {all ? "Show the 12 largest" : `Show all ${d.erosion.events.length} molecules`}
          </button>
        </p>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- Merck

function MerckSection({ d }: { d: Dataset }) {
  const h = d.headline.merck;
  const s = h.sitagliptin;
  const unpriced = d.merck.families.filter((f) => !f.inNadac);
  const priced = d.merck.families.filter((f) => f.inNadac);
  const w = d.watch;
  const rateMoves = w.watches.filter((x) => x.kind === "rate" && x.flag);
  return (
    <Section
      id="merck"
      title={`Januvia's rate was cut ${Math.abs(h.januvia.stepPct * 100).toFixed(0)}% on ${longDate(h.januvia.stepDate)}, and NADAC has priced ${s.genericPacks} generic sitagliptin packs since ${longDate(s.genericFirstWeek)}`}
      dek={`What NADAC shows for the ${d.merck.families.length} product families MSD has in Rx Market Pulse. ${h.priced} of them are retail products with a NADAC rate. The 100 mg generic is ${rate(s.genericRate100)} against Januvia's ${rate(s.januviaRate100)}, ${(s.ratio100 * 100).toFixed(0)}% of it. A patent date is not a launch date: the Orange Book data behind Rx Market Pulse gives core protection ending ${longDate(h.coreEnd)}, and this project does not establish why generics are priced earlier.`}
    >
      <Fig
        title="Weekly NADAC rate for one 100 mg tablet"
        sub="Januvia against generic sitagliptin. Each rate holds until the next weekly file."
        legend={<Legend items={[{ label: "Januvia 100 mg" }, { cls: "denim", label: "The January 2025 cut" }, { cls: "mute", label: "Generic sitagliptin 100 mg (median of packs)" }]} />}
        source="Source: CMS NADAC weekly rates. Generic packs are found by the name on the NADAC record, because a pack this new has no Medicaid product record yet."
        table={
          <table className="tbl">
            <caption>Weekly rates per 100 mg tablet</caption>
            <thead>
              <tr>
                <th scope="col">Week</th>
                <th scope="col" className="n">Januvia</th>
                <th scope="col" className="n">Generic</th>
              </tr>
            </thead>
            <tbody>
              {[...d.merck.sitagliptinWeekly].reverse().map((r) => (
                <tr key={r.d}>
                  <th scope="row">{shortDate(r.d)}</th>
                  <td className="n">{rate(r.januvia)}</td>
                  <td className="n">{r.generic == null ? "not priced" : rate(r.generic)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      >
        <SitagliptinChart merck={d.merck} coreEnd={h.coreEnd} stepDate={h.januvia.stepDate} />
      </Fig>

      <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Merck product families">
        <table className="tbl">
          <caption>Product families with a retail NADAC rate; the rate is for the pack with the most 2025 Medicaid units.</caption>
          <thead>
            <tr>
              <th scope="col">Family</th>
              <th scope="col">Pack</th>
              <th scope="col" className="n">2019</th>
              <th scope="col" className="n">2022</th>
              <th scope="col" className="n">2025</th>
              <th scope="col" className="n">Now</th>
              <th scope="col" className="n">Since 2019</th>
              <th scope="col">Core protection ends</th>
            </tr>
          </thead>
          <tbody>
            {priced.map((f) => (
              <tr key={f.family}>
                <th scope="row" className="nm">
                  {f.family.charAt(0) + f.family.slice(1).toLowerCase()}
                  <span className="sub-l">{f.area}, {usd(f.spend2025)} Medicaid 2025</span>
                </th>
                <td>{f.pack}</td>
                <td className="n">{rate(f.price2019)}</td>
                <td className="n">{rate(f.price2022)}</td>
                <td className="n">{rate(f.price2025)}</td>
                <td className="n">{rate(f.priceLatest)}</td>
                <td className="n">{f.changeSince2019 == null ? "n/a" : signedPct(f.changeSince2019)}</td>
                <td>{f.coreEnd ? monthLong(f.coreEnd.slice(0, 7)) : "not in the Orange Book"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="limits">
        <b>Not priced by NADAC:</b> {unpriced.map((f) => f.family.charAt(0) + f.family.slice(1).toLowerCase()).join(", ")}. These are infused, injected or specialty products that retail pharmacies do not buy at NADAC rates, so they carry {usd(unpriced.reduce((a, f) => a + f.spend2025, 0))} of the families&apos; 2025 Medicaid spend that this page cannot show a price for.
      </p>
      <div>
        <h3 style={{ fontFamily: "var(--serif)", fontSize: 17, margin: "0 0 6px" }}>The weekly watch</h3>
        <p className="stat-line">
          A GitHub Action downloads the current year&apos;s file every Thursday, checks it against the portal&apos;s own row count and follows these packs. Last run <b>{longDate(w.checked)}</b>:{" "}
          <b>{w.checks.filter((c) => c.ok).length} of {w.checks.length}</b> checks pass; {w.watches[0].found} generic sitagliptin packs priced; {rateMoves.length ? `a rate moved 5% or more: ${rateMoves.map((r) => r.name).join(", ")}` : "no watched rate has moved 5% or more"}.
        </p>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- two sources

function SourcesSection({ d }: { d: Dataset }) {
  const ps = periods(d.triangulation);
  const [pi, setPi] = useState(ps.findIndex((p) => p.y0 === 2022 && p.y1 === 2025));
  const p = ps[pi];
  const rows = ["Brand", "Generic", "All"].map((seg) => {
    const x = pair(d.triangulation, p.y0, p.y1, seg);
    return { label: seg === "All" ? "All matched packs" : seg, nadac: x.nadacEffect, medicaid: x.medicaidEffect, raw: x };
  });
  const rx = d.triangulation.rx.find((r) => r.y0 === p.y0 && r.y1 === p.y1);
  const brand = rows[0].raw;
  const hb = d.headline.triangulation.brand;
  return (
    <Section
      id="sources"
      title={`For brands the two sources agree: ${usd(hb.nadac, 1)} of price effect in NADAC, ${usd(hb.medicaid, 1)} in Medicaid, ${d.headline.triangulation.y0} to ${d.headline.triangulation.y1}`}
      dek="Rx Market Pulse reports a price effect from Medicaid spend per prescription. NADAC is an independent price. For the packs both cover, this section computes the same bridge two ways on the same volume: what pharmacies paid, and what Medicaid reimbursed."
    >
      <Fig
        title={`Price effect, ${p.label}`}
        sub="Change in price per unit times last year's Medicaid units, for packs priced by both sources."
        legend={<Legend items={[{ cls: "sq ink", label: "NADAC (what pharmacies paid)" }, { cls: "sq", label: "Medicaid (what it reimbursed)" }]} />}
        source={<>Source: CMS NADAC weekly rates; State Drug Utilization Data via Rx Market Pulse. Rx Market Pulse&apos;s published price effect for the whole market, {p.label}: {rx ? usd(rx.rxPriceEffect, 1) : "n/a"}.</>}
        table={
          <table className="tbl">
            <caption>Price effect by segment, {p.label}</caption>
            <thead>
              <tr>
                <th scope="col">Segment</th>
                <th scope="col" className="n">NADAC</th>
                <th scope="col" className="n">Medicaid</th>
                <th scope="col" className="n">Rank correlation</th>
                <th scope="col" className="n">Packs</th>
                <th scope="col" className="n">Share of spend covered</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <th scope="row">{r.label}</th>
                  <td className="n">{signedUsd(r.nadac, 2)}</td>
                  <td className="n">{signedUsd(r.medicaid, 2)}</td>
                  <td className="n">{r.raw.rankCorr.toFixed(2)}</td>
                  <td className="n">{int(r.raw.packs)}</td>
                  <td className="n">{pct(r.raw.coverageSpend)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      >
        <div className="chips" role="group" aria-label="Period" style={{ marginTop: 6 }}>
          {ps.map((x, i) => (
            <button key={x.label} type="button" aria-pressed={i === pi} onClick={() => setPi(i)}>
              {x.label}
            </button>
          ))}
        </div>
        <SourceBars rows={rows} />
      </Fig>
      <p className="limits">
        <b>Where they differ.</b> Brands: rank correlation of pack-level changes {brand.rankCorr.toFixed(2)}, and the packs cover {pct(brand.coverageSpend)} of that year&apos;s Medicaid spend. Generics move apart more: Medicaid&apos;s price falls faster than NADAC&apos;s, probably because Medicaid reimburses a dispensing fee as well as the ingredient cost, and the fee weighs most on cheap generics; that is a likely reason, not something the data shows. For generics Medicaid pays about twice NADAC per unit (scorecard C19), so the two are compared by change, not by level.
      </p>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- movers

function MoversSection({ d }: { d: Dataset }) {
  const keys = ["latest", ...Object.keys(d.movers.lists).filter((k) => k !== "latest").sort((a, b) => Number(b) - Number(a))];
  const [key, setKey] = useState("latest");
  const grid = useMemo(() => weekGrid(d.events), [d.events]);
  const list = d.movers.lists[key] ?? [];
  const bulkWeeks = grid.cells.filter((c) => c.bulk).length;
  return (
    <Section id="movers" title={`${int(d.movers.changes)} rates changed on ${longDate(d.movers.latestUpdate)}`} dek={`Rates are published every week but nearly all move once a month: ${bulkWeeks} of the ${grid.cells.length} weekly files since 2014 are monthly bulk updates with more than 1,000 changes. The latest moved ${int(d.movers.ups)} packs up and ${int(d.movers.downs)} down (${int(d.movers.material)} by 1% or more; the median move is ${signedPct(d.movers.medianChange, 2)}).`}>
      <Fig
        title="Every weekly file since 2014"
        sub="One square a week. Filled squares are monthly bulk updates; hollow squares are the quiet weeks between."
        legend={<Legend items={[{ cls: "sq ink", label: "Bulk update" }, { cls: "sq denim", label: "January bulk update" }, { cls: "sq", label: "Other week" }]} />}
        source="Source: CMS NADAC weekly rates. A bulk update is a week with more than 1,000 changes (scorecard C15)."
        table={
          <table className="tbl">
            <caption>Bulk updates per year</caption>
            <thead>
              <tr>
                <th scope="col">Year</th>
                <th scope="col" className="n">Weekly files</th>
                <th scope="col" className="n">Bulk updates</th>
              </tr>
            </thead>
            <tbody>
              {grid.years.map((y) => (
                <tr key={y}>
                  <th scope="row">{y}</th>
                  <td className="n">{grid.cells.filter((c) => c.y === y).length}</td>
                  <td className="n">{grid.cells.filter((c) => c.y === y && c.bulk).length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      >
        <WeekGrid years={grid.years} cells={grid.cells} cols={grid.cols} />
      </Fig>
      <div>
        <div className="chips" role="group" aria-label="Which moves to list">
          {keys.map((k) => (
            <button key={k} type="button" aria-pressed={k === key} onClick={() => setKey(k)}>
              {k === "latest" ? `Latest update (${shortDate(d.movers.latestUpdate)})` : `Largest in ${k}`}
            </button>
          ))}
        </div>
        <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Largest moves">
          <table className="tbl">
            <caption>The 15 changes worth most a year at 2025 Medicaid volume. Annual value is the price change times units, a size for ranking, not money anyone paid.</caption>
            <thead>
              <tr>
                <th scope="col">Pack</th>
                <th scope="col" className="n">From</th>
                <th scope="col" className="n">To</th>
                <th scope="col" className="n">Change</th>
                <th scope="col" className="n">Units</th>
                <th scope="col" className="n">Annual value</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={`${r.ndc}-${r.date}`}>
                  <th scope="row" className="nm">
                    {r.name.toLowerCase()}
                    <span className="sub-l">
                      <span className="ndc">{r.ndc}</span>
                      {[r.owner, r.segment !== "Generic" ? r.segment.toLowerCase() : null].filter(Boolean).map((x) => `, ${x}`).join("")}
                    </span>
                  </th>
                  <td className="n">{rate(r.from)}</td>
                  <td className="n">{rate(r.to)}</td>
                  <td className="n">{signedPct(r.pct, 1)}</td>
                  <td className="n">{r.units == null ? "n/a" : int(r.units)}</td>
                  <td className="n">{r.annualValue == null ? "n/a" : signedUsd(r.annualValue, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- quality

function QualitySection({ d }: { d: Dataset }) {
  const c = d.headline.checks;
  const byDim = new Map<string, typeof d.quality>();
  for (const q of d.quality) byDim.set(q.dimension, [...(byDim.get(q.dimension) ?? []), q]);
  const word = { pass: "Pass", warn: "Warn", fail: "Fail", info: "Measured" } as const;
  return (
    <Section id="quality" title={`${c.total} checks: ${c.pass} pass, ${c.warn === 0 && c.fail === 0 ? "none warn or fail" : `${c.warn} warn, ${c.fail} fail`}, ${c.info} are measurements`} dek="Each check says what it measured, the number and the rule it was held to. A measurement has no pass or fail rule; it is there because it changes how to read the data.">
      {[...byDim.entries()].map(([dim, items]) => (
        <div className="qgroup" key={dim}>
          <h3>{dim}</h3>
          <ul className="qlist">
            {items.map((q) => (
              <li key={q.id}>
                <div className="qrow">
                  <span className="st">
                    <Glyph status={q.status} />
                    {word[q.status]}
                  </span>
                  <div>
                    <span className="nm">
                      {q.id}. {q.name}
                    </span>
                    <span className="rs">{q.result}</span>
                    {q.note && (
                      <details>
                        <summary>Why it matters</summary>
                        <p>{q.note}</p>
                      </details>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- method and footer

function MethodSection({ d, repoUrl }: { d: Dataset; repoUrl?: string }) {
  const years = Object.entries(d.meta.expectedRows).filter(([k]) => /^nadac_\d{4}$/.test(k)).sort(([a], [b]) => a.localeCompare(b));
  const total = years.reduce((s, [, n]) => s + n, 0);
  return (
    <Section id="method" title="How the index is built, and what it cannot say">
      <p className="limits">
        <b>What this is not.</b> NADAC is what retail pharmacies pay before rebates. It is not a net price, not what a patient pays, and not what Medicaid pays. Clinic-administered and specialty products such as Keytruda are absent. An index is a way of reading price movement, not a price list, and a median across molecules is not a forecast for any one product.
      </p>
      <ol className="method">
        <li><b>Matched packs.</b> Each week&apos;s ratio compares only packs priced in two consecutive weeks, so a new or discontinued pack cannot move the index by itself.</li>
        <li><b>Weights.</b> The weighted index uses that calendar year&apos;s Medicaid units for each pack (State Drug Utilization Data via Rx Market Pulse), from 2019; 2026 uses 2025 units. The equal-weight index counts every pack once and goes back to December 2013.</li>
        <li><b>Errors left out.</b> A move above 10 times or below one tenth in a week is treated as a data error and dropped from both sides of the ratio (a few hundred of 17 million comparisons, scorecard C12); dropping the rule moves the latest value by about half a point (C13).</li>
        <li><b>Checked independently.</b> Three weekly ratios are recomputed in plain Python from raw rows and match to 1e-15 (C17); the index logic is also tested against a small dataset worked out by hand.</li>
        <li><b>Classes.</b> Brand and generic follow NADAC&apos;s own rate-setting class; the erosion section uses Rx Market Pulse&apos;s molecule records (C09 gives the agreement).</li>
      </ol>
      <div className="tbl-wrap">
        <table className="tbl" style={{ maxWidth: 560 }}>
          <caption>Rows loaded equal rows the portal reports, per year ({int(total)} rows in all)</caption>
          <thead>
            <tr>
              <th scope="col">Year</th>
              <th scope="col" className="n">Rows published</th>
              <th scope="col">Loaded</th>
            </tr>
          </thead>
          <tbody>
            {years.map(([k, n]) => (
              <tr key={k}>
                <th scope="row">{k.slice(6)}</th>
                <td className="n">{int(n)}</td>
                <td>equal</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="foot" id="end">
        <div className="foot-grid">
          <div>
            <h2>Sources</h2>
            <ul>
              {d.meta.sources.map((s) => (
                <li key={s.url + s.name}>
                  {s.name}, {s.publisher}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2>Take it further</h2>
            <ul>
              <li>
                <a href="/downloads/Price-Tracker.xlsx" download>
                  Price Tracker (Excel, {d.workbookKb} KB)
                </a>
                : pick a pack, compare it with its class, test a what-if for generic entry. Live formulas, checked in Excel against an independent calculation.
              </li>
              {repoUrl && (
                <li>
                  <a href={repoUrl}>The code and data on GitHub</a>, including the weekly watch and the scorecard as text.
                </li>
              )}
            </ul>
          </div>
          <div>
            <h2>Built by</h2>
            <p style={{ margin: 0 }}>Mohammad Uzair Khan. Part of a set with Rx Market Pulse, Trial Pipeline Benchmark and Field Force Planner.</p>
          </div>
        </div>
        <p className="disc">An independent case study built from public data. Not produced or endorsed by MSD or any company named. Built {longDate(d.meta.built)}.</p>
      </footer>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- the page

export function Report({ data: d, repoUrl }: { data: Dataset; repoUrl?: string }) {
  const h = d.headline;
  const bw = h.index.weighted;
  const gw = bw.generic;
  return (
    <>
      <a className="skip" href="#main">
        Skip to the report
      </a>
      <header className="bar">
        <div className="shell bar-in">
          <a className="brand" href="#top">
            Drug Price Watch
          </a>
          <nav aria-label="Sections">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`}>
                {s.label}
              </a>
            ))}
            <a className="dl" href="/downloads/Price-Tracker.xlsx" download>
              Price Tracker (Excel, {d.workbookKb} KB)
            </a>
          </nav>
          <details className="sections-menu">
            <summary className="btn">Sections</summary>
            <div className="menu">
              {SECTIONS.map((s) => (
                <a key={s.id} href={`#${s.id}`}>
                  {s.label}
                </a>
              ))}
              <a href="/downloads/Price-Tracker.xlsx" download>
                Price Tracker (Excel)
              </a>
            </div>
          </details>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="shell" tabIndex={-1}>
        <div className="hero" id="top">
          <p className="kicker">
            <b>US pharmacy drug prices, weekly,</b> from the CMS acquisition-cost survey (NADAC), {monthLong(h.firstWeek.slice(0, 7))} to {longDate(h.asOf)}. A commercial-analytics case study by Mohammad Uzair Khan.
          </p>
          <h1>
            Brand prices are {upDown(bw.brand)} since 2019, in steps. Generic prices are {upDown(gw)}.
          </h1>
          <p className="lede">
            NADAC is what pharmacies pay to buy a drug. {pct(h.seasonality.january)} of brand price rises of 2% or more land in January, and {pct(h.seasonality.janJul)} in January and July.
          </p>
          <FirstChart d={d} />
          <div className="watch">
            <p>
              <b>{int(h.latest.changes)} rates changed on {longDate(h.latest.date)}</b>, the latest monthly update. Rates are published weekly, but nearly all move once a month.
            </p>
            <p>
              <b>Januvia</b> 100 mg tablet: {rate(h.merck.januvia.from)} to {rate(h.merck.januvia.to)} on {longDate(h.merck.januvia.stepDate)} (<span className="dn">{signedPct(h.merck.januvia.stepPct)}</span>). NADAC has priced {h.merck.sitagliptin.genericPacks} generic sitagliptin packs since {longDate(h.merck.sitagliptin.genericFirstWeek)}, at {rate(h.merck.sitagliptin.genericRate100)} for 100 mg.
            </p>
          </div>
        </div>
        <IndexSection d={d} />
        <JanuarySection d={d} />
        <ErosionSection d={d} />
        <MerckSection d={d} />
        <SourcesSection d={d} />
        <MoversSection d={d} />
        <QualitySection d={d} />
        <MethodSection d={d} repoUrl={repoUrl} />
      </main>
    </>
  );
}

