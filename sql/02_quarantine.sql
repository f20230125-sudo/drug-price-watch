-- Typed copy of the staging table, and the rows that break a rule. Quarantined rows keep their reason and never
-- reach the facts, so an index is never built on a price that could not be read.
create or replace table nadac_typed as
select rid, source_year,
       ndc                                                    as ndc11,
       ndc_description                                        as description,
       try_cast(nadac_per_unit as double)                     as price,
       try_strptime(effective_date, '%m/%d/%Y')::date         as effective_date,
       try_strptime(as_of_date, '%m/%d/%Y')::date             as as_of,
       pricing_unit,
       upper(otc) = 'Y'                                       as otc,
       explanation_code,
       classification_for_rate_setting                        as cls
from stg_nadac;

create or replace table quarantine_nadac as
with flagged as (
    select *,
           case
               when ndc11 is null or not regexp_matches(ndc11, '^[0-9]{11}$') then 'NDC is not 11 digits'
               when price is null then 'price is not a number'
               when price <= 0 then 'price is zero or negative'
               when as_of is null then 'as-of date cannot be read'
               when effective_date is null then 'effective date cannot be read'
               when cls is null or cls not in ('B', 'G', 'B-ANDA', 'B-BIO') then 'unknown rate-setting class'
           end as reason
    from nadac_typed
),
dups as (
    select rid from (
        select rid, row_number() over (partition by ndc11, as_of order by effective_date desc, rid) as n
        from flagged where reason is null
    ) where n > 1
)
select f.* exclude (reason), f.reason from flagged f where f.reason is not null
union all
select f.* exclude (reason), 'same NDC twice in one week' as reason from flagged f join dups using (rid);
