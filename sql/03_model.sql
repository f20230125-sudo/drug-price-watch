-- Clean facts and dimensions. Fact = one price per NDC per week, only rows that passed the rules.

create or replace table fact_nadac as
select t.ndc11, t.as_of, t.price, t.effective_date, t.pricing_unit, t.otc, t.cls, t.explanation_code, t.source_year,
       -- NADAC rate-setting class: B brand, G generic, B-ANDA brand-labelled product approved as a generic,
       -- B-BIO biologic (a class added in 2022).
       case t.cls when 'B' then 'Brand' when 'G' then 'Generic' when 'B-ANDA' then 'Branded generic'
                  else 'Biologic' end as segment
from nadac_typed t
where t.rid not in (select rid from quarantine_nadac);

-- Rx Market Pulse extracts (see src/pw/rx_link.py): product attributes and Medicaid units by year.
create or replace table rx_attrs as
select * from read_csv('{ref_dir}/rx_ndc_attrs.csv.gz', header = true,
                       types = {'ndc11': 'VARCHAR', 'market_class': 'VARCHAR', 'family': 'VARCHAR',
                                'ingredient': 'VARCHAR', 'owner': 'VARCHAR', 'area': 'VARCHAR', 'is_biologic': 'BOOLEAN'});
create or replace table rx_units as
select * from read_csv('{ref_dir}/rx_units_year.csv.gz', header = true,
                       types = {'ndc11': 'VARCHAR', 'year': 'INTEGER', 'units': 'DOUBLE', 'rx': 'DOUBLE', 'spend': 'DOUBLE'});

-- One row per NDC: what it is called now, how long it has been priced, and what Rx Market Pulse knows about it.
create or replace table dim_ndc as
with agg as (
    select ndc11, min(as_of) as first_week, max(as_of) as last_week, count(*) as weeks,
           arg_max(pricing_unit, as_of) as pricing_unit, arg_max(cls, as_of) as cls,
           arg_max(segment, as_of) as segment, arg_max(otc, as_of) as otc
    from fact_nadac group by ndc11
),
names as (
    select ndc11, arg_max(description, as_of) as description
    from nadac_typed where rid not in (select rid from quarantine_nadac) group by ndc11
)
select a.*, n.description,
       r.market_class as rx_market_class, r.family, r.ingredient, r.owner, r.area, r.is_biologic,
       r.ndc11 is not null as in_rx
from agg a
join names n using (ndc11)
left join rx_attrs r using (ndc11);
