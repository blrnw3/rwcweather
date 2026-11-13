# Estimated daily history (v1)

Daily maximum temperature, minimum temperature and rainfall for 1 January 2009
through 26 December 2020, estimated from nearby stations and stored separately
from the measured `avg_extreme` record.

The series is only used when a request includes `est=1`. Climate normals stay
measured-only. Default reports (option off) do not read this table.

## Sources and conversions

Documented and versioned in `rwcwx/estimated/conversions.py` (`VERSION = "v1"`).

| Variable | Primary | Gap-fill |
| --- | --- | --- |
| Tmax | Redwood City COOP USC00047339, monthly linear | SFO, monthly offset (confidence B) |
| Tmin | Pulgas Ridge RAWS PUGC1 (IEM daily), monthly linear | SFO, monthly linear (confidence B) |
| Rain | PUGC1, annual ratio (~0.93) | SFO, annual ratio (~1.20) (confidence B) |

Coefficients were fitted on the 2021–2026 overlap with this site's measured
daily values (leave-one-year-out cross-validation). Pulgas IEM daily starts
6 December 2010, so Tmin and rain before that date are the SFO gap-fill.

## Regenerating

From a cache of IEM/ACIS files, or with `--fetch` to download missing files:

```
PYTHONPATH=. python -m rwcwx.estimated.generate \
  --cache-dir /path/to/cache --csv-out daily_estimated_v1.csv \
  --sql-out daily_estimated_v1.sql --summary-out summary.json
```

## Loading (not part of a dry run)

```
mysql wx < data/migrations/20261112_daily_estimated.sql
mysql wx < daily_estimated_v1.sql
```

A local or test process can also point at the CSV with `RWC_ESTIMATED_CSV`
without creating the table.
