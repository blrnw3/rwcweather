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
//    - temp.avg: explicitly stored, not derived. The station's daily mean
//      (computed from all 1-minute readings) runs below (max + min)/2 by
//      about 0.3 °C in winter to 1.3 °C in summer (annual mean -0.82 °C).
//      Each month's avg normal = (min + max)/2 + D, where D is the station's
//      2021-2026 monthly mean of (daily mean - daily midpoint).
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
//    - `source`, `period` and `notes` (list of short, user-facing sentences)
//      are shown verbatim on the climate page (/reports/climate).
//  Daily normals (used on the daily report) are interpolated from the monthly
//  values, anchored at mid-month.
// =============================================================================

export const CLIMATE_NORMALS = {
    placeholder: false,
    source: "PRISM 1991-2020 800 m normals, cell center 37.4667,-122.2667 "
        + "(station approx 37.470,-122.265, Emerald Lake Hills)",
    period: "1991-2020",
    // Shown on /reports/climate. Keep these short and non-technical; the
    // detailed adjustment reasoning lives in the header comment above.
    notes: [
        "Temperature and rainfall normals are PRISM Climate Group (Oregon State University) 1991-2020 "
            + "800 m gridded monthly normals, sampled at the grid cell centred on 37.4667, -122.2667 that "
            + "contains the station (approx. 37.470, -122.265, Emerald Lake Hills, ~125 m above sea level).",
        "Adjustments were made for the sensor's location (hillside thermal belt).",
        "The mean-temperature normal is adjusted for how the station averages: its daily mean (all 1-minute "
            + "readings) runs below (high + low) / 2, by about 0.3 °C in winter to 1.3 °C in summer, because "
            + "nights are long and afternoon peaks are brief.",
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
            avg: {
                unit: "degC",
                // (min + max)/2 + D, where D is the station's 2021-2026 monthly mean of (daily mean - daily midpoint)
                monthly: [10.88, 11.80, 12.88, 13.72, 15.89, 18.13, 19.15, 19.48, 19.53, 17.73, 13.70, 10.84],
            },
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
