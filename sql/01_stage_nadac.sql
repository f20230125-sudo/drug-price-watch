-- NADAC as published: one row per drug package (NDC) per weekly snapshot. Every column stays text, nothing is removed.
-- The portal's CSV headers are title case ("NDC Description"); normalize_names turns them into snake_case.
create or replace table stg_nadac as
select row_number() over ()                                                  as rid,
       regexp_extract(filename, 'nadac_([0-9]{4})[.]csv', 1)::integer        as source_year,
       ndc_description, ndc, nadac_per_unit, effective_date, pricing_unit, pharmacy_type_indicator, otc,
       explanation_code, classification_for_rate_setting, as_of_date,
       corresponding_generic_drug_nadac_per_unit                             as generic_nadac_per_unit,
       corresponding_generic_drug_effective_date                             as generic_effective_date
from read_csv({files}, all_varchar = true, normalize_names = true, filename = true, union_by_name = true);
