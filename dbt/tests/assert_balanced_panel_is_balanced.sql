-- The balanced panel must contain the same number of countries in every year.
select region
from {{ ref('mart_region_year_balanced') }}
group by region
having min(countries) <> max(countries)
