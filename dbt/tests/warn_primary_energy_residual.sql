{{ config(severity = 'warn') }}
-- Primary energy is not fully explained by fossil + low-carbon consumption in
-- some countries. This is a property of the source, not a pipeline bug, so it
-- warns instead of failing; reports/ quantifies it.
select iso_code, year, primary_energy_consumption,
       fossil_fuel_consumption + low_carbon_consumption as components
from {{ ref('fct_energy_country_year') }}
where primary_energy_consumption is not null
  and fossil_fuel_consumption is not null and low_carbon_consumption is not null
  and abs(primary_energy_consumption - (fossil_fuel_consumption + low_carbon_consumption))
      > {{ var('identity_tolerance') }} * primary_energy_consumption
