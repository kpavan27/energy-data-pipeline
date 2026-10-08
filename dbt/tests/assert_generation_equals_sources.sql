-- Electricity generation must equal the sum of generation by source.
with f as (
    select *,
        coal_electricity + oil_electricity + gas_electricity + nuclear_electricity
        + hydro_electricity + wind_electricity + solar_electricity + biofuel_electricity
        + other_renewable_exc_biofuel_electricity as by_source
    from {{ ref('fct_energy_country_year') }}
)
select iso_code, year, electricity_generation, by_source
from f
where electricity_generation is not null and by_source is not null
  and abs(electricity_generation - by_source)
      > {{ var('identity_tolerance') }} * greatest(abs(electricity_generation), 1)
