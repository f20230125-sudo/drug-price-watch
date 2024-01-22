-- Generic erosion in prices: what happens to a brand's NADAC rate, and to the generics' rates, once generics arrive?
--
-- Events are the 48 molecules Rx Market Pulse found (first quarter generics reach 10% of prescriptions; see
-- rx-analytics/sql/10_marts_erosion.sql). k = quarters since that entry quarter.
--   Brand index    = weighted price of the brand's packs relative to k = -1 (the quarter before entry), 100 = no change.
--   Generic index  = weighted price of the generics' packs relative to each pack's own first priced quarter at or after
--                    entry (100 = launch price), so a pack enters the index when NADAC first prices it.
-- Weights are Medicaid units in the entry year. Packs priced in the quarter and in the reference quarter only.

create or replace table rx_events as
select ingredient, brand_family, entry_quarter::date as entry_quarter, brand_index_before, brand_index_q4,
       brand_index_q8, generic_share_q4, generic_share_q8, molecule_index_q8, brand_run_rate_before_musd
from read_csv('{ref_dir}/rx_erosion_events.csv', header = true);

create or replace table nq as
select ndc11, year(as_of) * 4 + quarter(as_of) - 1 as qi, avg(price) as p
from fact_nadac group by 1, 2;

create or replace table erosion_members as
select e.ingredient, e.brand_family, e.entry_quarter,
       year(e.entry_quarter) * 4 + quarter(e.entry_quarter) - 1 as t0,
       d.ndc11, case when d.rx_market_class = 'Brand' then 'brand' else 'generic' end as side
from rx_events e
join dim_ndc d on (d.rx_market_class = 'Brand' and d.family = e.brand_family)
               or (d.rx_market_class = 'Generic' and d.ingredient = e.ingredient);

create or replace table erosion_path as
select m.ingredient, m.brand_family, m.side, n.qi - m.t0 as k, m.ndc11, n.p, coalesce(u.units, 1) as w
from erosion_members m
join nq n on n.ndc11 = m.ndc11 and n.qi between m.t0 - 8 and m.t0 + 12
left join rx_units u on u.ndc11 = m.ndc11 and u.year = least(greatest(year(m.entry_quarter), 2019), 2025);

create or replace table mart_erosion_price as
with ref as (
    select ingredient, brand_family, side, ndc11, p as p_ref, k as k_ref
    from erosion_path
    where side = 'brand' and k = -1
    union all
    -- a generic pack is measured from the first quarter it is priced at or after entry
    select ingredient, brand_family, side, ndc11, p, k from (
        select *, row_number() over (partition by ingredient, brand_family, ndc11 order by k) as rn
        from erosion_path where side = 'generic' and k >= 0
    ) where rn = 1
)
select a.ingredient, a.brand_family, a.side, a.k,
       100 * sum(a.w * a.p) / sum(a.w * r.p_ref) as price_index,
       count(*) as ndcs
from erosion_path a
join ref r using (ingredient, brand_family, side, ndc11)
where (a.side = 'brand' and a.k between -8 and 12) or (a.side = 'generic' and a.k between 0 and 12 and a.k >= r.k_ref)
group by all
order by ingredient, side, k;

-- Across molecules: the median path and the middle half.
create or replace table mart_erosion_cohort as
select side, k,
       quantile_cont(price_index, 0.5)  as median_index,
       quantile_cont(price_index, 0.25) as p25,
       quantile_cont(price_index, 0.75) as p75,
       count(*) as events
from mart_erosion_price
group by all
order by side, k;

-- One row per molecule: brand price vs brand spend, side by side.
create or replace table mart_erosion_events_price as
select e.ingredient, e.brand_family, e.entry_quarter, e.brand_run_rate_before_musd,
       max(p.price_index) filter (where p.side = 'brand' and p.k = 4)    as brand_price_q4,
       max(p.price_index) filter (where p.side = 'brand' and p.k = 8)    as brand_price_q8,
       max(p.price_index) filter (where p.side = 'generic' and p.k = 4)  as generic_price_q4,
       max(p.price_index) filter (where p.side = 'generic' and p.k = 8)  as generic_price_q8,
       e.brand_index_q4 as brand_spend_q4, e.brand_index_q8 as brand_spend_q8,
       count(distinct p.ndcs) filter (where p.side = 'brand' and p.k = -1)   as brand_ndcs,
       count(distinct p.ndcs) filter (where p.side = 'generic' and p.k = 0)  as generic_ndcs
from rx_events e
left join mart_erosion_price p on p.ingredient = e.ingredient and p.brand_family = e.brand_family
group by e.ingredient, e.brand_family, e.entry_quarter, e.brand_run_rate_before_musd, e.brand_index_q4, e.brand_index_q8
order by e.brand_run_rate_before_musd desc nulls last;

copy mart_erosion_price         to '{marts_dir}/erosion_price.csv'         (header, delimiter ',');
copy mart_erosion_cohort        to '{marts_dir}/erosion_cohort.csv'        (header, delimiter ',');
copy mart_erosion_events_price  to '{marts_dir}/erosion_events_price.csv'  (header, delimiter ',');
