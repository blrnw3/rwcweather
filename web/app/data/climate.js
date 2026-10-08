// =============================================================================
//  CLIMATE NORMALS for the Redwood City (rwcweather) station
//
//  !!! PLACEHOLDER VALUES !!!
//  Every number below is a DUMMY, round-number placeholder chosen only to be
//  roughly plausible for Redwood City so the climate-comparison UI can be built
//  and tested. They are NOT real normals and must be replaced with researched
//  long-term averages (e.g. NOAA 1991-2020 normals for a nearby station) before
//  the comparisons mean anything. While `placeholder` is true the site shows a
//  "placeholder climate normals" notice next to every comparison.
//
//  This is the ONLY place climate normals live. To drop in real values:
//    1. Replace the `monthly` arrays (Jan..Dec, 12 numbers each).
//    2. Optionally set `annual` (otherwise it is derived: sum of the monthly
//       values for totals, mean of the monthly values for averages) and, for
//       rain, `waterYear` (Oct-Sep; otherwise the same derived sum).
//    3. Fill in `source` / `period`, and set `placeholder: false`.
//
//  Shape:   NORMALS[var][dailyStat] = { unit, monthly[12], annual?, waterYear? }
//    - `var` and `dailyStat` are the API's variable and daily-aggregation names
//      (/api/var/all_periods/<var>/<dailyStat>/), so lookups are direct.
//    - Values are in the station's NATIVE (database/API) units, NOT display
//      units: temperature in degC, rainfall in inches, wind speed in mph.
//      The UI converts to the visitor's chosen units.
//    - temp.min / temp.max are the normal daily low / high for the month;
//      temp.avg is the normal daily mean (if omitted it is derived as the mean
//      of temp.min and temp.max, the usual NOAA convention).
//    - rain.total is the normal monthly precipitation total.
//    - wind.avg is the normal monthly mean wind speed (optional; no comparison
//      is shown for variables or stats that have no entry here).
//  Daily normals (used on the daily report) are interpolated from the monthly
//  values, anchored at mid-month.
// =============================================================================

export const CLIMATE_NORMALS = {
    placeholder: true,
    source: "PLACEHOLDER - dummy values, pending research",
    period: "PLACEHOLDER",

    normals: {
        temp: {
            //        Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
            min: {
                unit: "degC",
                monthly: [4.0, 5.0, 6.0, 7.0, 9.0, 11.0, 12.5, 13.0, 12.0, 9.5, 6.0, 4.0],
            },
            max: {
                unit: "degC",
                monthly: [14.5, 16.5, 18.5, 20.5, 23.0, 26.0, 27.5, 27.5, 27.0, 23.5, 18.0, 14.5],
            },
            // avg omitted: derived as (min + max) / 2
        },
        rain: {
            total: {
                unit: "in",
                monthly: [4.0, 4.0, 3.0, 1.5, 0.5, 0.1, 0.02, 0.05, 0.2, 1.0, 2.5, 3.5],
                // annual / waterYear omitted: derived as the sum of monthly (20.37 in)
            },
        },
        wind: {
            avg: {
                unit: "mph",
                monthly: [3.0, 3.5, 4.0, 4.5, 5.0, 5.0, 5.0, 4.5, 4.0, 3.5, 3.0, 3.0],
            },
        },
    },
};
