-- Regional low-carbon electricity share over a balanced panel: only countries
-- that report generation and low-carbon generation in every year of the
-- window. Without this, coverage changes look like trends: Africa goes from 4
-- countries with electricity-mix data in 1999 to 56 in 2000, and its
-- unbalanced low-carbon share "jumps" from 9.2% to 20.5%.
{% set start = var('panel_start_year') %}
{% set end = var('panel_end_year') %}
with panel as (
    select iso_code
    from {{ ref('fct_energy_country_year') }}
    where year between {{ start }} and {{ end }}
      and low_carbon_electricity is not null
      and electricity_generation is not null
    group by iso_code
    having count(distinct year) = {{ end - start + 1 }}
)
select
    d.region,
    f.year,
    count(*)                                                                    as countries,
    sum(f.electricity_generation)                                               as electricity_generation_twh,
    100 * sum(f.low_carbon_electricity) / nullif(sum(f.electricity_generation), 0)  as low_carbon_share_elec_pct
from {{ ref('fct_energy_country_year') }} f
join panel using (iso_code)
join {{ ref('dim_country') }} d using (iso_code)
where f.year between {{ start }} and {{ end }}
  and d.region <> 'Unmapped'
group by all
