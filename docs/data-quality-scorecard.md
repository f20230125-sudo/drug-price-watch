# Data-quality scorecard

21 checks run against the warehouse built from the NADAC files. 12 pass, 0 warn, 0 fail, 9 are measurements with no rule.

Regenerate with `python -m pw.dq`. Failures and warnings come first.

## C01 Rows loaded equal rows published, per year

- **Status:** pass
- **Result:** 14 of 14 years match the count the portal reports
- **Rule:** every year equal
- **Note:** 17,317,268 rows, 2013-2026.

## C02 Weekly snapshots are consecutive

- **Status:** pass
- **Result:** 673 snapshots; gaps in days: 6d x1, 7d x671
- **Rule:** no gap longer than 8 days
- **Note:** A missing week would turn two weeks of price change into one 'weekly' move in the index.

## C03 Every row has a readable NDC, price, dates and rate-setting class

- **Status:** pass
- **Result:** 0 rows set aside
- **Rule:** 0 rows set aside
- **Note:** Rows that break a rule go to quarantine_nadac with the reason and never reach the facts. A first version of the rule threw away 2,885 'B-BIO' rows (a class NADAC added in 2022); reading them as a real class fixed it.

## C04 Prices are positive numbers

- **Status:** pass
- **Result:** 0 rows are not
- **Rule:** 0

## C05 Pricing unit is one of EA (each), ML (millilitre) or GM (gram)

- **Status:** pass
- **Result:** EA 14,433,759, GM 1,006,966, ML 1,876,543
- **Rule:** no other unit
- **Note:** A price per tablet cannot be compared with a price per millilitre; each NDC keeps one unit.

## C06 One price per NDC per week

- **Status:** pass
- **Result:** 0 duplicated pairs
- **Rule:** 0

## C07 Latest snapshot is recent and no snapshot is dated in the future

- **Status:** pass
- **Result:** latest 2026-10-14 (2 days old); 0 future-dated rows
- **Rule:** newest snapshot within 14 days; 0 future
- **Note:** NADAC is republished weekly; the weekly job in .github/workflows re-checks this.

## C13 The weighted all-market index barely depends on the outlier rule

- **Status:** pass
- **Result:** latest value 107.0 with the rule, 106.5 without
- **Rule:** within 1 index point
- **Note:** If dropping the rule moved the index a lot, the rule would be doing the work. It does not.

## C16 Every week since 2019 has at least 5,000 weighted packs in the all-market index

- **Status:** pass
- **Result:** 0 weeks below
- **Rule:** 0

## C17 Weekly index ratio recomputed independently in Python

- **Status:** pass
- **Result:** 3 weeks checked; largest difference 3.55e-15
- **Rule:** below 1e-9
- **Note:** Python re-derives the ratio from raw rows with no window functions, to catch a SQL mistake.

## C19 Medicaid spend per unit against NADAC price per unit (generics, 2025)

- **Status:** pass
- **Result:** median ratio 2.28
- **Rule:** between 0.8 and 3
- **Note:** If the two sources counted units differently the ratio would sit near 0.01 or 100. A ratio above 1 is expected: Medicaid reimburses ingredient cost plus a dispensing fee, and the fee weighs most on cheap generics. That fee is also why the Medicaid price effect is compared with NADAC's, not equated.

## C20 Change counts by year add up to the change table

- **Status:** pass
- **Result:** 3,462,731 vs 3,462,731
- **Rule:** equal

## C08 A pack keeps the same brand/generic class over time

- **Status:** info
- **Result:** 86 of 62,780 packs change class at some point
- **Rule:** report
- **Note:** Usually a brand that lost exclusivity and was re-listed, or a reclassification. Each week's price is grouped by the class it had that week; the latest class is used for labels.

## C09 NADAC's class agrees with Rx Market Pulse's brand/generic flag

- **Status:** info
- **Result:** 93.2% of 53,367 packs agree
- **Rule:** report
- **Note:** They are different definitions: NADAC sets a rate class per drug; Rx Market Pulse uses the Medicaid product record. Examples that differ: unbranded insulin lispro (a biologic sold under the brand's licence) and eye-drop brands sold as unapproved generics. Brand/generic charts use NADAC's class; the molecule-level work (erosion) uses Rx Market Pulse's.

## C10 How much of 2025 Medicaid volume has a NADAC price

- **Status:** info
- **Result:** 93.1% of units, 71.8% of spend
- **Rule:** report
- **Note:** NADAC prices what retail pharmacies buy, so clinic-administered and specialty products (Keytruda, most biologics) are absent. Spend coverage is far below unit coverage because those products are expensive.

## C11 NADAC packs that appear in the Medicaid product records

- **Status:** info
- **Result:** 85.1% of 62,780
- **Rule:** report
- **Note:** Packs not in the records have no brand family, owner or therapeutic area, so they appear in the all-market and brand/generic indexes only.

## C12 Week-on-week moves above 10x or below 0.1x

- **Status:** info
- **Result:** 364 of 17,247,190 comparisons (0.0021%)
- **Rule:** left out of the indexes
- **Note:** Treated as data errors and excluded, in the numerator and the denominator alike.

## C14 Brand rates start drifting by under 0.5% from 2024

- **Status:** info
- **Result:** share of brand changes under 0.5%: 19.6% in 2022, 86.3% in 2024
- **Rule:** report
- **Note:** A change in how NADAC is published, not a market event. Counts of 'changes' jump about five-fold; this project counts 'material' changes (1% or more) and says so wherever it counts.

## C15 Rates move in monthly bulk updates

- **Status:** info
- **Result:** weeks with over 1,000 changes per year (2015-2025): 2015: 12, 2016: 12, 2017: 12, 2018: 13, 2019: 12, 2020: 12, 2021: 12, 2022: 12, 2023: 12, 2024: 12, 2025: 12
- **Rule:** report
- **Note:** Published weekly, repriced monthly in practice. 'Latest movers' therefore means the latest bulk update.

## C18 Generic-entry events that NADAC can price

- **Status:** info
- **Result:** 27 of 48 molecules have priced brand packs; 35 of 48 have priced generic packs
- **Rule:** report
- **Note:** The rest are infused, injected or specialty products that retail pharmacies do not buy at NADAC rates. The erosion chart states how many molecules sit behind each line.

## C21 Merck product families with a retail NADAC price

- **Status:** info
- **Result:** 8 of 14
- **Rule:** report
- **Note:** Keytruda, Winrevair, Bridion, Zerbaxa, Prevymis and Welireg are not priced by NADAC; the page lists them as such.
