-- Electricity demand must equal generation plus net imports.
select iso_code, year, electricity_demand, electricity_generation, net_elec_imports
from {{ ref('fct_energy_country_year') }}
where electricity_demand is not null and electricity_generation is not null and net_elec_imports is not null
  and abs(electricity_demand - (electricity_generation + net_elec_imports))
      > {{ var('identity_tolerance') }} * greatest(abs(electricity_demand), 1)
