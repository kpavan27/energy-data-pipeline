-- Long format (release, country, year, metric, value): the shape the
-- release-to-release comparison needs. Nulls are dropped, so a value that
-- appears or disappears between releases shows up as an insert or delete.
unpivot (
    select release_date, iso_code, year,
    {%- for m in var('energy_measures') %}
        {{ m }}{{ "," if not loop.last }}
    {%- endfor %}
    from {{ ref('stg_energy') }}
)
on {{ var('energy_measures') | join(', ') }}
into name metric value value
