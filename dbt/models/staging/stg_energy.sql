-- One row per release, country and year. Typed, countries only: OWID's
-- regional and income-group aggregates (no ISO code, or an OWID_ code) are
-- dropped so that sums over countries never double count.
select
    cast(_release as date)          as release_date,
    _source_commit                  as source_commit,
    iso_code,
    country                         as country_name,
    cast(year as integer)           as year,
{%- for m in var('energy_measures') %}
    try_cast({{ m }} as double)     as {{ m }}{{ "," if not loop.last }}
{%- endfor %}
from {{ source('bronze', 'energy') }}
where iso_code is not null
  and iso_code not like 'OWID%'
