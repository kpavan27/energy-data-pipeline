-- One row per release pair and metric. The ratio percentiles separate two
-- very different kinds of revision:
--   * a methodology change rescales values by about the same factor
--     (at least 100 updates, tight p10-p90 band, median ratio away from 1);
--   * routine data revisions touch fewer values, by varying amounts.
with r as (
    select *, new_value / nullif(old_value, 0) as ratio
    from {{ ref('fct_metric_revisions') }}
),
summary as (
    select
        old_release,
        new_release,
        metric,
        count(*) filter (where change_type = 'insert')      as inserted,
        count(*) filter (where change_type = 'delete')      as deleted,
        count(*) filter (where change_type = 'update')      as updated,
        count(*) filter (where change_type = 'unchanged')   as unchanged,
        median(abs(rel_change)) filter (where change_type = 'update')                         as median_abs_rel_change,
        median(ratio) filter (where change_type = 'update' and abs(old_value) > 1)            as median_ratio,
        quantile_cont(ratio, 0.1) filter (where change_type = 'update' and abs(old_value) > 1) as p10_ratio,
        quantile_cont(ratio, 0.9) filter (where change_type = 'update' and abs(old_value) > 1) as p90_ratio
    from r
    group by all
)
select
    *,
    updated / nullif(updated + unchanged, 0)                as share_updated,
    coalesce(
        updated >= 100
        and p90_ratio - p10_ratio < 0.01
        and abs(median_ratio - 1) > 0.005,
        false
    )                                                       as looks_like_rescaling
from summary
