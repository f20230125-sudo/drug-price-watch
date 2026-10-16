-- Price indexes.
--
-- Week-on-week relative price of every NDC that was priced in two consecutive weeks (a matched-model index:
-- new products enter the index the week after they first appear, discontinued ones leave, and a pack that is
-- only compared with itself cannot change the index because of mix).
--   Weighted index  = chained Laspeyres. Weekly ratio = sum(w * price) / sum(w * previous price), with w = that
--                     calendar year's Medicaid units for the NDC (Rx Market Pulse). Medicaid units exist for
--                     2019 on, so the weighted index starts at 2019-01-02 = 100; 2026 uses 2025 units.
--   Equal-weight    = chained Jevons (geometric mean of relatives), every NDC counts once. It goes back to the first
--   index             NADAC week (2013-12-05) and reads as "the typical pack" rather than "the typical dollar".
-- A relative above 10x or below 0.1x in one week is treated as a data error and left out of both (counted in the
-- scorecard, and tests/test_index.py checks the index barely moves without the rule).

create or replace table wk as
select ndc11, as_of, price, segment,
       lag(price) over w                                       as prev_price,
       date_diff('day', lag(as_of) over w, as_of)              as gap_days
from fact_nadac
window w as (partition by ndc11 order by as_of);

create or replace table wk_rel as
select r.ndc11, r.as_of, r.price, r.prev_price, r.segment, r.price / r.prev_price as rel,
       (r.price / r.prev_price > 10 or r.price / r.prev_price < 0.1) as extreme,
       u.units as w
from wk r
left join rx_units u on u.ndc11 = r.ndc11 and u.year = least(year(r.as_of), 2025)
where r.prev_price is not null and r.gap_days <= 10;

-- Groups an NDC belongs to. 'All' is every NDC; the others use the NDC's NADAC class, therapeutic area and brand family.
create or replace table idx_groups as
select ndc11, 'segment' as kind, segment as grp from dim_ndc
union all select ndc11, 'segment', 'All' from dim_ndc
union all select ndc11, 'area', area from dim_ndc where area is not null and area <> 'Unclassified'
union all select ndc11, 'family', family from dim_ndc where family is not null and owner = 'Merck (MSD)';

create or replace table idx_week_ratio as
select g.kind, g.grp, r.as_of,
       sum(r.w * r.price)      filter (where r.w > 0 and not r.extreme)
         / nullif(sum(r.w * r.prev_price) filter (where r.w > 0 and not r.extreme), 0)  as ratio_w,
       exp(avg(ln(r.rel)) filter (where not r.extreme))                                 as ratio_j,
       count(*) filter (where not r.extreme)                                            as n_matched,
       count(*) filter (where r.w > 0 and not r.extreme)                                as n_weighted,
       count(*) filter (where r.extreme)                                                as n_extreme
from wk_rel r join idx_groups g using (ndc11)
group by all;

create or replace table mart_index_week as
with cum as (
    select kind, grp, as_of, ratio_w, ratio_j, n_matched, n_weighted, n_extreme,
           exp(sum(ln(ratio_j)) over (partition by kind, grp order by as_of))                         as cj,
           exp(sum(ln(ratio_w)) filter (where as_of >= date '2019-01-01')
                   over (partition by kind, grp order by as_of))                                       as cw
    from idx_week_ratio
)
select kind, grp, as_of,
       100 * cj / first_value(cj) over (partition by kind, grp order by as_of)                        as equal_weight,
       case when as_of >= date '2019-01-01'
            then 100 * cw / first_value(cw ignore nulls) over (partition by kind, grp order by as_of)
       end                                                                                              as weighted,
       n_matched, n_weighted, n_extreme
from cum
order by kind, grp, as_of;

create or replace table mart_index_month as
select kind, grp, date_trunc('month', as_of)::date as month,
       avg(equal_weight) as equal_weight, avg(weighted) as weighted,
       count(*) as weeks, round(avg(n_matched)) as ndcs
from mart_index_week
group by all
order by kind, grp, month;

copy mart_index_month to '{marts_dir}/index_month.csv' (header, delimiter ',');
