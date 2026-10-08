// =============================================================================
//  CLIMATE NORMALS for the Redwood City (rwcweather) station
//
//  Source: PRISM Climate Group (Oregon State University) 1991-2020 800 m
//  monthly normals (dataset an91/r2207h, normals/9120.b, version M5), sampled
//  at the grid cell centred 37.4667, -122.2667, which contains the station
//  (approx 37.470, -122.265, Emerald Lake Hills, ~125 m above sea level).
//  Period: 1991-2020. Methods, candidate stations and validation notes are in
//  the research write-up (climate-normals/METHODS.md, built 2026-10-08).
//
//    - temp.min / temp.max: PRISM tmin / tmax at the cell.
//    - temp.avg: not stored; derived as (min + max) / 2 (NOAA convention).
//    - rain.total: PRISM ppt at the cell (617 mm = 24.30 in/yr). Precipitation
//      is the most location-sensitive normal: the surrounding 3x3 cells range
//      21.2-26.7 in/yr. The water-year (Oct-Sep) normal equals the annual.
//    - wind: deliberately omitted. There is no representative normal for this
//      sheltered, low-mounted anemometer, so wind shows no comparison.
//
//  This is the ONLY place climate normals live.
//
//  Shape:   NORMALS[var][dailyStat] = { unit, monthly[12], annual?, waterYear? }
//    - `var` and `dailyStat` are the API's variable and daily-aggregation names
//      (/api/var/all_periods/<var>/<dailyStat>/), so lookups are direct.
//    - Values are in the station's NATIVE (database/API) units, NOT display
//      units: temperature in degC, rainfall in inches, wind speed in mph.
//      The UI converts to the visitor's chosen units.
//    - `annual` is optional (derived: sum of monthly for totals, mean of
//      monthly for averages); `waterYear` (rain only) defaults to the sum.
//    - Variables / stats with no entry simply get no comparison.
//    - Set `placeholder: true` to flag values as dummies in the UI.
//  Daily normals (used on the daily report) are interpolated from the monthly
//  values, anchored at mid-month.
// =============================================================================

export const CLIMATE_NORMALS = {
    placeholder: false,
    source: "PRISM 1991-2020 800 m normals, cell center 37.4667,-122.2667 "
        + "(station approx 37.470,-122.265, Emerald Lake Hills)",
    period: "1991-2020",

    normals: {
        temp: {
            //        Jan    Feb    Mar    Apr    May    Jun    Jul    Aug    Sep    Oct    Nov    Dec
            min: {
                unit: "degC",
                monthly: [5.62, 6.21, 6.82, 7.63, 9.48, 11.02, 12.29, 12.51, 11.92, 10.43, 7.53, 5.47],
            },
            max: {
                unit: "degC",
                monthly: [15.40, 16.84, 18.68, 20.24, 22.84, 26.13, 27.15, 27.50, 27.74, 24.95, 19.08, 15.28],
            },
            // avg omitted: derived as (min + max) / 2
        },
        rain: {
            total: {
                unit: "in",
                monthly: [4.82, 4.76, 3.68, 1.74, 0.65, 0.17, 0.02, 0.05, 0.08, 1.02, 2.29, 5.03],
                annual: 24.30,
                waterYear: 24.30,
            },
        },
        // wind: intentionally omitted (no representative normal) - no comparison shown.
    },
};
