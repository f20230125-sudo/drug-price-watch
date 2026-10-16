-- Merck (MSD) lens: what NADAC shows for the 14 product families Rx Market Pulse follows.
-- NADAC covers retail-dispensed products only, so infused or clinic-administered ones (Keytruda, Bridion, Zerbaxa)
-- have no row here; that is stated on the page, not hidden.

create or replace table rx_merck as
select family, franchise, area, spend_2025, status, core_end::date as core_end
from read_csv('{ref_dir}/rx_merck_families.csv', header = true, types = {'core_end': 'DATE'});

-- The pack that carries each family in Medicaid: the NADAC-priced NDC with the most 2025 units.
create or replace table merck_pack as
select * exclude (rk) from (
    select d.family, d.ndc11, d.description, d.segment, u.units as units_2025,
           row_number() over (partition by d.family order by u.units desc) as rk
    from dim_ndc d
    join rx_units u on u.ndc11 = d.ndc11 and u.year = 2025
    where d.owner = 'Merck (MSD)'
) where rk = 1;

create or replace table mart_merck as
with latest_month as (select max(month) as m from mart_index_month where kind = 'family'),
brand_now as (
    select weighted as brand_index_now from mart_index_month, latest_month
    where kind = 'segment' and grp = 'Brand' and month = latest_month.m
),
fam_now as (
    select grp as family, weighted as family_index_now, equal_weight as family_equal_now
    from mart_index_month, latest_month where kind = 'family' and month = latest_month.m
),
last_wk as (select max(as_of) as as_of from fact_nadac)
select r.family, r.franchise, r.area, r.spend_2025, r.status, r.core_end,
       p.ndc11 as pack_ndc, p.description as pack, p.segment as pack_segment,
       n19.p as price_2019, n22.p as price_2022, n25.p as price_2025, f.price as price_latest,
       f.price / n19.p - 1 as change_since_2019,
       fn.family_index_now, bn.brand_index_now,
       p.ndc11 is not null as in_nadac
from rx_merck r
left join merck_pack p on p.family = r.family
left join nadac_year n19 on n19.ndc11 = p.ndc11 and n19.y = 2019
left join nadac_year n22 on n22.ndc11 = p.ndc11 and n22.y = 2022
left join nadac_year n25 on n25.ndc11 = p.ndc11 and n25.y = 2025
left join fact_nadac f on f.ndc11 = p.ndc11 and f.as_of = (select as_of from last_wk)
left join fam_now fn on fn.family = r.family
cross join brand_now bn
order by r.spend_2025 desc;

-- Sitagliptin (Januvia's molecule), found by the name on the NADAC record. Packs that first appeared this year have no
-- Medicaid product record yet, so they carry no ingredient and an ingredient-based search misses them (the first
-- version of this project did, and reported "no generic sitagliptin priced"; the weekly watch caught it).
create or replace table mart_sitagliptin_summary as
select count(*) filter (where segment = 'Generic') as generic_packs,
       count(distinct left(ndc11, 5)) filter (where segment = 'Generic') as generic_labelers,
       min(first_week) filter (where segment = 'Generic') as generic_first_week,
       count(*) filter (where segment <> 'Generic') as brand_packs
from dim_ndc where description like 'SITAGLIPTIN%' or description like 'JANUVIA%' or description like 'JANUMET%'
                or description like 'ZITUVIO%';

create or replace table mart_sitagliptin_rates as
with last_wk as (select max(as_of) as as_of from fact_nadac),
priced as (
    select d.description, f.price, regexp_extract(d.description, '([0-9]+ MG) TABLET$', 1) as strength,
           case when d.description like 'SITAGLIPTIN PHOSPHATE % MG TABLET' then 'generic'
                when d.description like 'JANUVIA % MG TABLET' then 'januvia' end as side
    from fact_nadac f join dim_ndc d using (ndc11), last_wk
    where f.as_of = last_wk.as_of
)
select g.strength, g.n as generic_packs, g.rate as generic_rate, j.rate as januvia_rate, g.rate / j.rate as ratio
from (select strength, count(*) as n, median(price) as rate from priced where side = 'generic' and strength <> '' group by 1) g
join (select strength, median(price) as rate from priced where side = 'januvia' and strength <> '' group by 1) j using (strength)
order by cast(split_part(strength, ' ', 1) as integer);

-- What a "typical" molecule did after generics arrived, in price and in spend (spend is Rx Market Pulse's index,
-- brand spend relative to the year before entry). Used for the labelled scenario on the page, not as a forecast.
create or replace table mart_scenario as
select k,
       max(median_index) filter (where side = 'brand') as brand_price_median,
       max(p25) filter (where side = 'brand') as brand_price_p25,
       max(p75) filter (where side = 'brand') as brand_price_p75,
       max(events) filter (where side = 'brand') as brand_events,
       max(median_index) filter (where side = 'generic') as generic_price_median,
       max(events) filter (where side = 'generic') as generic_events
from mart_erosion_cohort
group by k
order by k;

create or replace table mart_scenario_spend as
select quantile_cont(brand_index_q4, 0.5) as brand_spend_q4_median,
       quantile_cont(brand_index_q8, 0.5) as brand_spend_q8_median,
       count(brand_index_q4) as events_q4, count(brand_index_q8) as events_q8
from rx_events;

copy mart_sitagliptin_summary to '{marts_dir}/sitagliptin_summary.csv' (header, delimiter ',');
copy mart_sitagliptin_rates   to '{marts_dir}/sitagliptin_rates.csv'   (header, delimiter ',');
copy mart_merck          to '{marts_dir}/merck.csv'          (header, delimiter ',');
copy mart_scenario       to '{marts_dir}/scenario.csv'       (header, delimiter ',');
copy mart_scenario_spend to '{marts_dir}/scenario_spend.csv' (header, delimiter ',');
