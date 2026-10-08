// =============================================================================
//  CLIMATE NORMALS for the Redwood City (rwcweather) station
//
//  Source: PRISM Climate Group (Oregon State University) 1991-2020 800 m
//  monthly normals (dataset an91/r2207h, normals/9120.b, version M5), sampled
//  at the grid cell centred 37.4667, -122.2667, which contains the station
//  (approx 37.470, -122.265, Emerald Lake Hills, ~125 m above sea level).
//  Period: 1991-2020. Full methods, candidate stations and the calibration
//  analysis are in the research write-up (climate-normals/METHODS.md, §9).
//
//    - temp.min: PRISM tmin + 1.5 degC (+/-0.3) in every month, calibrated
//      against the station: in all 69 months of Jan 2021 - Sep 2026 the
//      station's nights ran warmer than PRISM. Likely the hillside thermal
//      belt, possibly also some sensor warmth at night.
//    - temp.max: raw PRISM tmax (the station shows no consistent offset).
//    - temp.avg: not stored; derived as (min + max) / 2, so it uses the
//      calibrated min.
//    - rain.total: raw PRISM ppt (617 mm = 24.30 in/yr; the station has
//      averaged 0.99x PRISM). Rain is the most location-sensitive normal:
//      neighbouring cells range 21.2-26.7 in/yr. Water year = annual.
//    - No elevation (lapse-rate) correction: the cell is at ~120 m vs the
//      station's ~125 m (~0.03 degC), and PRISM already models elevation,
//      so correcting again would double-count.
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
//    - `source`, `period` and `notes` (list of sentences) are shown verbatim on
//      the climate page (/reports/climate), so update them with the values.
//  Daily normals (used on the daily report) are interpolated from the monthly
//  values, anchored at mid-month.
// =============================================================================

export const CLIMATE_NORMALS = {
    placeholder: false,
    source: "PRISM 1991-2020 800 m normals, cell centre 37.4667,-122.2667 "
        + "(station approx 37.470,-122.265, Emerald Lake Hills); daily low calibrated to the station (+1.5 °C)",
    period: "1991-2020",
    notes: [
        "Temperature and rainfall normals are PRISM Climate Group (Oregon State University) 1991-2020 "
            + "800 m gridded monthly normals, sampled at the grid cell centred on 37.4667, -122.2667 that "
            + "contains the station (approx. 37.470, -122.265, Emerald Lake Hills, ~125 m above sea level).",
        "Daily lows are station-calibrated: PRISM's minimum plus 1.5 °C (±0.3) in every month. Comparing "
            + "69 months of station data (Jan 2021 – Sep 2026) with PRISM, the station's nights were warmer every "
            + "month, most likely because it sits in the hillside thermal belt, and possibly partly from some "
            + "sensor warmth at night.",
        "Daily highs and rainfall are raw PRISM: highs show no consistent offset, and the station's rain "
            + "has averaged 0.99 times PRISM.",
        "No elevation (lapse-rate) correction was applied: the grid cell is at about 120 m and the station at "
            + "about 125 m, a difference of only ~0.03 °C, and PRISM already accounts for elevation, so it would "
            + "be double-counted.",
        "Mean temperature is the average of the normal daily low and high. The water year runs from "
            + "1 October to 30 September.",
        "Rainfall is the most location-sensitive normal: the neighbouring 800 m cells range from about "
            + "21.2 to 26.7 inches a year.",
        "Wind speed has no representative normal for this station's sheltered, low-mounted anemometer, "
            + "so it is not included.",
    ],

    normals: {
        temp: {
            //        Jan    Feb    Mar    Apr    May    Jun    Jul    Aug    Sep    Oct    Nov    Dec
            min: {
                unit: "degC",
                // PRISM tmin + 1.5 degC (station-calibrated; raw PRISM Jan = 5.62)
                monthly: [7.12, 7.71, 8.32, 9.13, 10.98, 12.52, 13.79, 14.01, 13.42, 11.93, 9.03, 6.97],
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
