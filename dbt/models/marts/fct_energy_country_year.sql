-- Latest release only: one row per country and year, with CO2 joined in and
-- shares recomputed from the additive measures (never averaged downstream).
with energy as (
    select *
    from {{ ref('stg_energy') }}
    where release_date = (select max(release_date) from {{ ref('stg_energy') }})
)
select
    e.iso_code,
    e.year,
    e.release_date,
{%- for m in var('energy_measures') %}
    e.{{ m }},
{%- endfor %}
    c.co2_mt,
    100 * e.fossil_fuel_consumption / nullif(e.primary_energy_consumption, 0)  as fossil_share_energy_pct,
    100 * e.low_carbon_electricity / nullif(e.electricity_generation, 0)       as low_carbon_share_elec_pct,
    -- Mt CO2 per TWh is numerically kg CO2 per kWh.
    c.co2_mt / nullif(e.primary_energy_consumption, 0)                        as co2_kg_per_kwh_primary,
    1e6 * e.primary_energy_consumption / nullif(e.population, 0)              as primary_energy_kwh_per_capita
from energy e
left join {{ ref('stg_co2') }} c using (iso_code, year)
