# Drug Price Watch

What US pharmacies pay for prescription drugs, week by week since 2013: how prices move, when they step, what happens to a brand's price when generics arrive, and whether two independent price sources agree. Built from {{factRows|int}} weekly NADAC rates on {{packs|int}} drug packs, a weekly check that runs by itself, and an Excel model with every result as a live formula.

> The README is generated: `python -m pw.readme` fills every number from `dashboard/public/data/headline.json`, and a test fails if this file is out of date.

## What it found

All figures are from the build of {{asOf|date}} (data to that week). Weighted means weighted by Medicaid units; the index starts at 100 in January 2019.

- **Brand prices rose in steps; generic prices fell.** Since January 2019 the Medicaid-weighted index of brand packs is {{index.weighted.brand|up_pct0}} and of generic packs {{index.weighted.generic|up_pct0}}. Counting every pack once (back to December 2013), brands are {{index.equalWeight.brand|up_pct0}} and generics {{index.equalWeight.generic|up_pct0}}.
- **Brand price steps follow the calendar.** Of {{seasonality.brandSteps|int}} brand price increases of 2% or more (2014 to 2025), {{seasonality.january|pct0}} happened in January and {{seasonality.july|pct0}} in July; together {{seasonality.janJul|pct0}}, against 17% if they were spread evenly.
- **After generics arrive a brand keeps its price and loses its volume.** Across {{erosion.brandPriced|int}} molecules whose brand packs NADAC prices, the median brand price index is {{erosion.brandPriceQ8|f1}} eight quarters after generic entry (100 = the quarter before), while the brand's Medicaid spend, from Rx Market Pulse, falls to {{erosion.brandSpendQ8|f1}} (same scale). Generic prices fall to {{erosion.genericPriceQ8|f1}} after eight quarters and {{erosion.genericPriceQ12|f1}} after twelve (100 = launch price).
- **Two price sources agree where they should.** For brand packs both sources cover, the Medicaid unit price effect 2022 to 2025 is {{triangulation.brand.medicaid|usd_b}} and the NADAC effect {{triangulation.brand.nadac|usd_b}} (rank correlation {{triangulation.brand.corr|f2}}). Rx Market Pulse's published "price" effect for the whole market is {{triangulation.rxPriceEffect|usd_b}}. The packs both sources cover carry {{triangulation.coverageSpend|pct0}} of 2025 Medicaid spend.
- **Januvia and generic sitagliptin (Merck).** Januvia 100 mg's rate stepped down {{merck.januvia.stepPct|abs_pct0}} in the NADAC week of {{merck.januvia.stepDate|date}} (from {{merck.januvia.from|usd2}} to {{merck.januvia.to|usd2}} a tablet). NADAC has priced {{merck.sitagliptin.genericPacks|int}} generic sitagliptin packs from {{merck.sitagliptin.genericLabelers|int}} labelers since {{merck.sitagliptin.genericFirstWeek|date}}; the 100 mg generic is {{merck.sitagliptin.genericRate100|usd2}} against Januvia's {{merck.sitagliptin.januviaRate100|usd2}}. The Orange Book data behind Rx Market Pulse shows core protection ending {{merck.coreEnd|date}}; a patent date is not a launch date, and this project does not establish why the generics were priced earlier.
- **Rates are published weekly but move monthly.** The latest bulk update, {{latest.date|date}}, changed {{latest.changes|int}} packs ({{latest.ups|int}} up, {{latest.downs|int}} down; {{latest.material|int}} by 1% or more).

## Contents

| Path | What it is |
|---|---|
| `src/pw/` | fetch, build, scorecard, JSON export, Excel builder, weekly watch, README renderer |
| `sql/` | the warehouse in eight numbered SQL files: stage, quarantine, model, five mart files |
| `data/ref/` | committed inputs: dataset ids read from the portal, the Rx Market Pulse extracts, the watch list |
| `data/marts/` | committed results (CSV), including the {{checks.total|int}}-check scorecard |
| `excel/Price-Tracker.xlsx` | pick a pack, compare it with its class, run a what-if for generic entry; live formulas |
| `dashboard/` | the Next.js site (data in `public/data/`) |
| `tests/` | pytest: index math against hand calculation, quarantine rules, warehouse tie-outs, workbook, weekly watch |
| `.github/workflows/weekly-watch.yml` | Thursday job: download, check, summarise, commit |
| `docs/` | `data-quality-scorecard.md`, `case-studies.md` (what went wrong and how it was found), `design.md` |

## How it works

1. **Fetch.** Fourteen yearly NADAC files from data.medicaid.gov, each checked against the row count the portal reports ({{stagedRows|int}} rows; every year ties).
2. **Quarantine.** Rows with an unreadable NDC, price, date or class go to a table with the reason and never reach the facts.
3. **Model.** One price per pack per week; each pack joined to Rx Market Pulse's product record (brand family, owner, therapeutic area) and its Medicaid units.
4. **Index.** A matched-model chained index: each week's ratio compares only packs priced in two consecutive weeks. The weighted version weights by that year's Medicaid units (2019 on); the equal-weight version counts every pack once. Moves above 10x or below 0.1x in a week are treated as errors and left out ({{checks.total|int}} scorecard checks, including a re-derivation of three weekly ratios in plain Python that matches to 1e-15).
5. **Events, erosion, agreement, Merck lens.** See `sql/05` to `sql/08`.
6. **Watch.** `python -m pw.refresh` downloads the current year, checks it, follows the packs in `data/ref/watch.csv` and appends to `data/marts/weekly_log.csv`.

## Run it

```
pip install -r requirements.txt
set PYTHONPATH=src
python -m pw.fetch          # 14 yearly files, about 1.6 GB, a few minutes
python -m pw.build          # warehouse (about 5 minutes)
python -m pw.dq             # scorecard
python -m pw.export_json    # JSON for the site
python -m pw.workbook       # Excel model (then tools/recalc.ps1 to store Excel's own values in the file)
python -m pw.readme         # this file
python -m pytest            # tests
cd dashboard && npm ci && npm run build && npm run start
```

`python -m pw.rx_link --refresh` re-extracts the Rx Market Pulse tables from a local copy of that project; the committed extracts are enough to build.

## Limits, stated plainly

- NADAC is what retail pharmacies paid before rebates. It is not a net price, and it does not cover clinic-administered products such as Keytruda ({{merck.priced|int}} of {{merck.families|int}} Merck families have a NADAC price).
- Medicaid units cover 2019 on, so the weighted index starts then; the equal-weight index goes back to 2013 and reads as "the typical pack", not "the typical dollar".
- Since spring 2024 brand rates drift by hundredths of a percent at each update. That is a change in publication, not a market event; counts of changes use a 1% threshold.
- The erosion lines cover only molecules NADAC prices; each chart says how many sit behind it. A median across molecules is not a forecast for any product.
- Medicaid pays more per unit than NADAC because it reimburses a dispensing fee as well as ingredient cost (scorecard check C19 gives the median ratio); the two are compared by change, not by level.
- A pack first priced this year has no Medicaid product record yet, so it has no ingredient or owner. See `docs/case-studies.md` for the sitagliptin miss this caused and how it was caught.

Data: CMS NADAC (data.medicaid.gov) and State Drug Utilization Data via [Rx Market Pulse](https://github.com/f20230125-sudo/rx-market-pulse). Not affiliated with CMS or any company named.
