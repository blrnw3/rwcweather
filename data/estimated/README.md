# Estimated daily history (v2)

Daily maximum temperature, minimum temperature and rainfall for 1 January 2011
through 26 December 2020, estimated from Pulgas Ridge RAWS (PUGC1, IEM daily)
and stored separately from the measured `avg_extreme` record.

The series is only used when a request includes `est=1`. Climate normals stay
measured-only. Default reports (option off) do not read this table.

## Sources and conversions

Documented and versioned in `rwcwx/estimated/conversions.py` (`VERSION = "v2"`).

| Variable | Source | Method |
| --- | --- | --- |
| Tmax | Pulgas Ridge RAWS PUGC1 (IEM daily) | Monthly linear |
| Tmin | PUGC1 | Monthly linear |
| Rain | PUGC1 | Annual ratio (~0.93) |

Coefficients were fitted on the 2021–2026 overlap with this site's measured
daily values (leave-one-year-out cross-validation). Days or variables missing
from Pulgas are left unestimated; there is no gap-fill from another station.
Pulgas IEM Tmax is missing for all of 2013 and parts of 2012 and 2014.

## Regenerating

From a cache of IEM files, or with `--fetch` to download missing files:

```
PYTHONPATH=. python -m rwcwx.estimated.generate \
  --cache-dir /path/to/cache --csv-out daily_estimated_v2.csv \
  --sql-out daily_estimated_v2.sql --summary-out summary.json
```

## Loading (not part of a dry run)

```
mysql wx < data/migrations/20261112_daily_estimated.sql
mysql wx < daily_estimated_v2.sql
```

A local or test process can also point at the CSV with `RWC_ESTIMATED_CSV`
without creating the table.
