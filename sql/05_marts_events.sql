-- Price-change events: a week in which an NDC's NADAC rate differs from the week before.
-- Relatives above 10x / below 0.1x are data errors and are left out (same rule as the index).
-- annual_impact = (new price - old price) x that year's Medicaid units: what the change is worth over a year at
-- Medicaid volume, a size for ranking changes, not money anyone paid.

create or replace table fact_change as
select r.ndc11, r.as_of, r.prev_price, r.price, r.rel - 1 as pct, r.segment,
       d.description, d.area, d.family, d.owner, d.ingredient,
       year(r.as_of)::integer as y, month(r.as_of)::integer as m,
       r.w as units, (r.price - r.prev_price) * r.w as annual_impact
from wk_rel r join dim_ndc d using (ndc11)
where not r.extreme and abs(r.price - r.prev_price) > 1e-9;

-- One row per year and segment: how many packs were priced, how many moved, how far.
create or replace table mart_events_year as
with priced as (
    select year(as_of) as y, segment, count(distinct ndc11) as ndcs_priced, count(*) as ndc_weeks
    from fact_nadac group by all
),
moved as (
    select y, segment,
           count(*) as changes,
           count(*) filter (where pct > 0) as ups,
           count(*) filter (where pct < 0) as downs,
           -- Since spring 2024 brand rates drift by a few hundredths of a percent at every update, so raw counts
           -- jump without any market event. "Material" means a move of 1% or more either way.
           count(*) filter (where abs(pct) >= 0.01) as material_changes,
           count(*) filter (where pct >= 0.01) as material_ups,
           count(*) filter (where pct <= -0.01) as material_downs,
           count(*) filter (where pct >= 0.02) as steps_up_2pct,
           quantile_cont(pct, 0.5) filter (where pct > 0) as median_up,
           quantile_cont(pct, 0.5) filter (where pct < 0) as median_down,
           sum(annual_impact) filter (where pct > 0) as impact_up,
           sum(annual_impact) filter (where pct < 0) as impact_down
    from fact_change group by all
)
select p.y, p.segment, p.ndcs_priced, p.ndc_weeks, coalesce(m.changes, 0) as changes, coalesce(m.ups, 0) as ups,
       coalesce(m.downs, 0) as downs, coalesce(m.material_changes, 0) as material_changes,
       coalesce(m.material_ups, 0) as material_ups, coalesce(m.material_downs, 0) as material_downs,
       coalesce(m.steps_up_2pct, 0) as steps_up_2pct,
       m.median_up, m.median_down, m.impact_up, m.impact_down,
       coalesce(m.changes, 0) * 1.0 / p.ndc_weeks as share_of_ndc_weeks_changed
from priced p left join moved m using (y, segment)
order by p.y, p.segment;

-- Brand price steps (increases of 2% or more) by calendar month: do they cluster in January and July?
create or replace table mart_events_season as
select segment, m,
       count(*) filter (where pct >= 0.02) as steps_up_2pct,
       count(*) filter (where pct <= -0.02) as steps_down_2pct,
       count(*) as changes
from fact_change
where y between 2014 and 2025
group by all
order by segment, m;

-- Rates are published every week but nearly all of them move once a month (a bulk update of ~28,000 packs); the
-- weeks between change a handful. "Latest" therefore means the most recent week with more than 1,000 changes.
create or replace table latest_update as
select max(as_of) as as_of from (select as_of from fact_change group by as_of having count(*) > 1000);

-- The biggest changes by annual value in each of the last 3 years, and the latest monthly update's moves.
create or replace table mart_movers as
with ranked as (
    select 'year' as scope, y::varchar as label, c.ndc11, c.description, c.segment, c.owner, c.family, c.as_of,
           c.prev_price, c.price, c.pct, c.units, c.annual_impact,
           row_number() over (partition by y order by abs(annual_impact) desc) as rk
    from fact_change c
    where c.y >= 2023 and c.annual_impact is not null
),
latest as (
    select 'latest' as scope, (select as_of from latest_update)::varchar as label, c.ndc11, c.description, c.segment,
           c.owner, c.family, c.as_of, c.prev_price, c.price, c.pct, c.units, c.annual_impact,
           row_number() over (order by abs(c.annual_impact) desc) as rk
    from fact_change c
    where c.as_of = (select as_of from latest_update) and c.annual_impact is not null
)
select * exclude (rk) from ranked where rk <= 15
union all
select * exclude (rk) from latest where rk <= 15;

copy mart_events_year   to '{marts_dir}/events_year.csv'   (header, delimiter ',');
copy mart_events_season to '{marts_dir}/events_season.csv' (header, delimiter ',');
copy mart_movers        to '{marts_dir}/movers.csv'        (header, delimiter ',');
