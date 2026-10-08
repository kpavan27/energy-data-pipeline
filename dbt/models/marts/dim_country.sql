-- Countries present in the latest energy release, enriched with UN M49 regions.
-- Territories the ISO table does not cover keep region = 'Unmapped' rather
-- than being dropped, so no energy data silently disappears.
with latest as (
    select distinct iso_code, country_name
    from {{ ref('stg_energy') }}
    where release_date = (select max(release_date) from {{ ref('stg_energy') }})
)
select
    l.iso_code,
    l.country_name,
    coalesce(c.region, 'Unmapped')      as region,
    coalesce(c.subregion, 'Unmapped')   as subregion,
    c.iso_code is not null              as has_iso_region
from latest l
left join {{ ref('stg_country_codes') }} c using (iso_code)
