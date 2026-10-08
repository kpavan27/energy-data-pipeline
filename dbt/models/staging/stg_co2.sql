-- Latest CO2 release, countries only. Units: million tonnes CO2.
with latest as (
    select max(_release) as release from {{ source('bronze', 'co2') }}
)
select
    iso_code,
    cast(year as integer)                   as year,
    try_cast(co2 as double)                 as co2_mt,
    try_cast(co2_including_luc as double)   as co2_including_luc_mt
from {{ source('bronze', 'co2') }}
where _release = (select release from latest)
  and iso_code is not null
  and iso_code not like 'OWID%'
