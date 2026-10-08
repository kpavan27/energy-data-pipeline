-- Regional totals for the latest release. Shares are recomputed from summed
-- TWh rather than averaged, so large countries carry their real weight.
-- Only countries reporting both numerator and denominator are included in a share.
select
    d.region,
    f.year,
    count(*)                                                as countries,
    count(*) filter (where f.low_carbon_electricity is not null
                       and f.electricity_generation is not null) as countries_with_electricity_mix,
    sum(f.primary_energy_consumption)                       as primary_energy_twh,
    sum(f.electricity_generation)                           as electricity_generation_twh,
    sum(f.co2_mt)                                           as co2_mt,
    100 * sum(f.low_carbon_electricity) filter (where f.electricity_generation is not null)
        / nullif(sum(f.electricity_generation) filter (where f.low_carbon_electricity is not null), 0)
                                                            as low_carbon_share_elec_pct,
    sum(f.co2_mt) filter (where f.primary_energy_consumption is not null)
        / nullif(sum(f.primary_energy_consumption) filter (where f.co2_mt is not null), 0)
                                                            as co2_kg_per_kwh_primary
from {{ ref('fct_energy_country_year') }} f
join {{ ref('dim_country') }} d using (iso_code)
group by all
