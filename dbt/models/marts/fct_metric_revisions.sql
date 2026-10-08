-- Change data capture between consecutive releases. Every (country, year,
-- metric) cell that exists in either release is classified as an insert,
-- delete, update or unchanged. Float noise below 1e-6 relative is ignored.
with pairs as (
    select previous_release_date as old_release, release_date as new_release
    from {{ ref('dim_release') }}
    where previous_release_date is not null
),
old_side as (
    select p.old_release, p.new_release, l.iso_code, l.year, l.metric, l.value
    from pairs p
    join {{ ref('int_energy_long') }} l on l.release_date = p.old_release
),
new_side as (
    select p.old_release, p.new_release, l.iso_code, l.year, l.metric, l.value
    from pairs p
    join {{ ref('int_energy_long') }} l on l.release_date = p.new_release
),
compared as (
    select
        old_release,
        new_release,
        iso_code,
        year,
        metric,
        o.value     as old_value,
        n.value     as new_value
    from old_side o
    full join new_side n using (old_release, new_release, iso_code, year, metric)
)
select
    *,
    case
        when old_value is null then 'insert'
        when new_value is null then 'delete'
        when abs(new_value - old_value) > 1e-9 + 1e-6 * abs(old_value) then 'update'
        else 'unchanged'
    end                                                         as change_type,
    new_value - old_value                                       as abs_change,
    (new_value - old_value) / nullif(abs(old_value), 0)         as rel_change
from compared
