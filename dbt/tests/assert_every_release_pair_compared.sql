-- Each release after the first must have been compared with its predecessor.
select r.release_date
from {{ ref('dim_release') }} r
where r.previous_release_date is not null
  and not exists (
      select 1 from {{ ref('mart_revision_summary') }} s
      where s.new_release = r.release_date and s.old_release = r.previous_release_date
  )
