# Estimated daily history (v5)

Daily maximum temperature, minimum temperature and rainfall for 1 January 2011
through 26 December 2020, estimated from nearby stations and stored separately
from the measured `avg_extreme` record.

The series is only used when a request includes `est=1`. Climate normals stay
measured-only. Default reports (option off) do not read this table.

## Sources and conversions

Documented and versioned in `rwcwx/estimated/conversions.py` (`VERSION = "v5"`).

Pulgas Ridge RAWS (PUGC1, IEM daily) is the primary source for every variable.
Days or variables missing from Pulgas, or rejected by quality control, are
filled from a calibrated secondary:

| Variable | Primary | First fill | Last fill |
| --- | --- | --- | --- |
| Tmax | PUGC1 monthly linear | Redwood City COOP USC00047339, monthly linear (confidence B) | SFO, monthly offset (confidence C) |
| Tmin | PUGC1 monthly linear | COOP monthly linear (confidence B) | SFO monthly linear (confidence C) |
| Rain | PUGC1 annual ratio (~0.93) | COOP annual ratio (~1.25) (confidence B) | SFO annual ratio (~1.20) (confidence C) |

Coefficients were fitted on the 2021–2026 overlap with this site's measured
daily values (leave-one-year-out cross-validation). Each row records its
`source` and `confidence` so reports can say which station was used. Pulgas
IEM temperatures are missing for all of 2013 and parts of 2012 and 2014;
those gaps are filled where the COOP or SFO has a value.

Quality control rejects a Pulgas rain total above 1 in when it is more than
3× the larger of the same-day COOP and SFO raw totals, or when both of those
stations are dry. A Pulgas Tmin is rejected when it differs by more than 8 °C
from the COOP (else SFO) converted estimate for that day. A Pulgas Tmax is
rejected only when it differs by more than 8 °C from both the COOP and SFO
converted estimates; if either comparator is missing, Pulgas is kept. Rejected
days are filled from the same secondary chain and marked confidence B or C.

## Regenerating

From a cache of IEM/ACIS files, or with `--fetch` to download missing files:

```
PYTHONPATH=. python -m rwcwx.estimated.generate \
  --cache-dir /path/to/cache --csv-out daily_estimated_v5.csv \
  --sql-out daily_estimated_v5.sql --summary-out summary.json
```

## Loading (not part of a dry run)

```
mysql wx < data/migrations/20261112_daily_estimated.sql
mysql wx < daily_estimated_v5.sql
```

A local or test process can also point at the CSV with `RWC_ESTIMATED_CSV`
without creating the table.
