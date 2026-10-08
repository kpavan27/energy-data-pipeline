select
    release_date,
    source_commit,
    row_number() over (order by release_date)            as release_number,
    lag(release_date) over (order by release_date)       as previous_release_date,
    release_date = max(release_date) over ()             as is_latest
from (select distinct release_date, source_commit from {{ ref('stg_energy') }})
