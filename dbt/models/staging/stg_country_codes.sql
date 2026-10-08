select
    "ISO3166-1-Alpha-3"     as iso_code,
    "CLDR display name"     as display_name,
    "Region Name"           as region,
    "Sub-region Name"       as subregion
from {{ source('bronze', 'country_codes') }}
where "ISO3166-1-Alpha-3" is not null
  and _release = (select max(_release) from {{ source('bronze', 'country_codes') }})
