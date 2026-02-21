# Case studies: what went wrong, and how it was found

The order to tell these in if you have ten minutes: the sitagliptin miss (1), the rule that was too strict (2), the "weekly" data that is monthly (4), the two price sources (5). The rest are shorter.

## 1. I said there was no generic sitagliptin, and there were 28

**What happened.** The Merck section first read "no generic sitagliptin pack is priced yet", computed by counting packs whose ingredient is sitagliptin and whose class is not brand. The count was zero. I wrote it into the draft headline.

**How it was found.** I wrote the weekly watch (`pw.refresh`) to look for any pack whose NADAC description contains SITAGLIPTIN. On its first live run it flagged five descriptions. Querying the warehouse by name found 28 generic packs from three labelers, first priced on 5 Aug 2026.

**Why.** Ingredient comes from Rx Market Pulse's product record, and a pack only gets a record once Medicaid sees a claim for it. A pack priced for ten weeks has no ingredient. The ingredient search was blind to every new product, which are exactly the ones that matter when you are watching a launch.

**Fix and guard.** The Merck mart now finds sitagliptin by the name on the NADAC record; a regression test asserts that the by-name count is above 20 while the by-ingredient count is zero (so the test fails if someone "simplifies" it back); scorecard check C22 reports how many packs first priced in 2026 have no product record (1,964). The real finding turned out better than the wrong one: the generic's rate is 36% of Januvia's, and Januvia's own rate has not moved.

**What it taught.** A claim of "none found" deserves the same suspicion as a surprising number: check that the search could have found one.

## 2. A rule that was too strict threw away 2,885 rows

**What happened.** The first load put 2,885 rows into quarantine, all for one reason: "unknown rate-setting class". I had assumed three classes (B, G, B-ANDA).

**How it was found.** Because quarantine keeps the reason, one distinct value showed up instead of a pile. The class was B-BIO, which NADAC added in 2022 for biologics (Zarxio is one). A real class, not bad data.

**Fix.** B-BIO is accepted as its own segment ("Biologic"); the quarantine test now includes it as a case that must pass; the scorecard says the first version of the rule dropped these rows.

## 3. A test that was wrong, not the code

**What happened.** My hand-worked example for "an outlier is left out of the index" expected the index to be unchanged by the outlier pack. The test failed: 108.95, not 110.

**What it was.** The outlier pack (flat for two weeks, then 20 times in one week) still carries weight in the weeks before it, which shifts those weeks' ratios (260/250 = 1.04, not 210/200 = 1.05). The SQL was right and my arithmetic was wrong. The test now spells out the hand calculation (100 x 1.04 x 220/210).

## 4. Rates are published weekly but move monthly

**What happened.** "Biggest movers in the latest week" came back empty. The latest week in the file has no changes at all.

**What it was.** NADAC publishes a snapshot every week, but nearly all rates move once a month in a bulk update of about 28,000 packs; the weeks between change a handful. Twelve such weeks a year, every year since 2015 (scorecard C15).

**Fix.** "Latest" means the latest week with more than 1,000 changes. The same profiling found a second thing: from spring 2024 brand rates start drifting by hundredths of a percent at every update (the share of brand changes under 0.5% goes from 20% in 2022 to 86% in 2024), so raw counts of changes jump five-fold with no market event. Counts now use a 1% threshold and the break is a scorecard check (C14).

## 5. Do two price sources agree?

**What happened.** Rx Market Pulse's price-volume-mix bridge says the price effect 2022 to 2025 was +$2.7B. NADAC gives an independent price. Comparing them directly was not like for like: Rx's "price" is spend per prescription, which also moves with strength, pack size and days' supply.

**What I did.** Defined the same bridge two ways on the same packs and the same final-year volume: NADAC's price per unit against Medicaid's spend per unit. For brands both sources cover they agree ($2.8B vs $2.5B, rank correlation 0.77). For the whole matched set NADAC shows more ($1.5B vs $0.7B), and for generics the Medicaid price falls more than NADAC's. The likely reason is the dispensing fee, which dominates cheap generics and is in Medicaid's number but not in NADAC's. That is reported as a likely reason, not shown.

## 6. Excel checked against Excel

The Price Tracker and the Field Force sizing model are not trusted because they look right. A PowerShell script drives Excel itself through six input scenarios and a separate Python script, sharing no code with the workbook builder, recomputes every cell. Two faults surfaced in the tooling rather than the workbook: PowerShell variable names are case-insensitive, so a typed `$Scenarios` path parameter silently swallowed my parsed `$scenarios` list; and a rank formula that builds a text criterion (`COUNTIF(range, "<"&x)`) loses precision beyond 15 digits, so the stored values are rounded to 8 decimals first.

## 7. Using more of the erosion data

The first erosion chart measured a generic pack from its price in the entry quarter, which only 16 molecules had. Measuring each generic pack from the first quarter it is priced at or after entry raised that to 31 molecules without changing the method. Each line says how many molecules sit behind it.
