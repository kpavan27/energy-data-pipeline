-- Fossil consumption must equal coal + oil + gas within tolerance.
select iso_code, year, fossil_fuel_consumption,
       coal_consumption + oil_consumption + gas_consumption as components
from {{ ref('fct_energy_country_year') }}
where fossil_fuel_consumption is not null
  and coal_consumption is not null and oil_consumption is not null and gas_consumption is not null
  and abs(fossil_fuel_consumption - (coal_consumption + oil_consumption + gas_consumption))
      > {{ var('identity_tolerance') }} * greatest(abs(fossil_fuel_consumption), 1)
