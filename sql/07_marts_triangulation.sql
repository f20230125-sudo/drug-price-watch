-- Do two independent price sources agree?
--
-- Rx Market Pulse says spend per prescription moved by X between two years (its "price" effect). That figure is
-- not a clean price: it also moves with strength, pack size and days' supply. NADAC gives a clean price per unit.
-- For the packs priced by NADAC and billed to Medicaid in both years, this table computes the same bridge
-- two ways, on the same packs and the same final-year volume:
--   nadac_effect    = sum (NADAC price y1 - NADAC price y0) x Medicaid units y1        what pharmacies paid
--   medicaid_effect = sum (Medicaid spend per unit y1 - y0) x Medicaid units y1        what Medicaid reimbursed
-- and sets Rx Market Pulse's published price effect beside them.
-- A pack must have at least 20 weekly rates in a year for that year's average rate to count.

create or replace table rx_pvm as
select y0, y1, segment, spend_0, spend_1, change, volume, mix, price, new_products, lost_products
from read_csv('{ref_dir}/rx_pvm.csv', header = true);

create or replace table nadac_year as
select ndc11, year(as_of)::integer as y, avg(price) as p
from fact_nadac group by ndc11, year(as_of) having count(*) >= 20;

create or replace table tri_pairs as
select * from (values (2019, 2022), (2022, 2025), (2019, 2025), (2024, 2025)) t(y0, y1);

create or replace table tri_ndc as
select p.y0, p.y1, n0.ndc11, d.segment,
       n0.p as p0, n1.p as p1,
       u0.units as q0, u1.units as q1, u0.spend / u0.units as m0, u1.spend / u1.units as m1,
       (n1.p / n0.p between 0.1 and 10) and ((u1.spend / u1.units) / (u0.spend / u0.units) between 0.1 and 10) as usable
from tri_pairs p
join nadac_year n0 on n0.y = p.y0
join nadac_year n1 on n1.y = p.y1 and n1.ndc11 = n0.ndc11
join rx_units u0 on u0.year = p.y0 and u0.ndc11 = n0.ndc11 and u0.units > 0 and u0.spend > 0
join rx_units u1 on u1.year = p.y1 and u1.ndc11 = n0.ndc11 and u1.units > 0 and u1.spend > 0
join dim_ndc d on d.ndc11 = n0.ndc11;

create or replace table tri_total as
select year as y1, sum(units) as units, sum(spend) as spend from rx_units group by year;

create or replace table mart_triangulation as
with scoped as (
    select y0, y1, ndc11, 'All' as seg, p0, p1, q0, q1, m0, m1 from tri_ndc where usable
    union all
    select y0, y1, ndc11, segment, p0, p1, q0, q1, m0, m1 from tri_ndc where usable and segment in ('Brand', 'Generic')
),
ranked as (
    select *, rank() over (partition by y0, y1, seg order by p1 / p0) as rp,
              rank() over (partition by y0, y1, seg order by m1 / m0) as rm
    from scoped
)
select r.y0, r.y1, r.seg as segment,
       count(*)                                                   as ndcs,
       sum(r.q1 * r.m1) / any_value(t.spend)                      as coverage_of_spend,
       sum(r.q1) / any_value(t.units)                             as coverage_of_units,
       sum((r.p1 - r.p0) * r.q1)                                  as nadac_effect,
       sum((r.m1 - r.m0) * r.q1)                                  as medicaid_effect,
       sum(r.p1 * r.q1) / sum(r.p0 * r.q1) - 1                    as nadac_change,
       sum(r.m1 * r.q1) / sum(r.m0 * r.q1) - 1                    as medicaid_change,
       corr(r.rp, r.rm)                                           as rank_corr,
       sum(r.q1 * r.m1)                                           as matched_spend_y1
from ranked r
join tri_total t on t.y1 = r.y1
group by r.y0, r.y1, r.seg
order by r.y0, r.y1, r.seg;

create or replace table mart_triangulation_rx as
select y0, y1, price as rx_price_effect, change as rx_spend_change, spend_0, spend_1
from rx_pvm where segment = 'All market' and (y0, y1) in (select y0, y1 from tri_pairs)
order by y0, y1;

copy mart_triangulation    to '{marts_dir}/triangulation.csv'    (header, delimiter ',');
copy mart_triangulation_rx to '{marts_dir}/triangulation_rx.csv' (header, delimiter ',');
