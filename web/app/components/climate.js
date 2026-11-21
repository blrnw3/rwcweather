import { Link as ChakraLink, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { CLIMATE_NORMALS } from "../data/climate";
import { formatObs } from "../format";
import { OBS } from "./conf";
import { seasonMonths } from "./seasons";

// Climate comparison, modelled on nw3weather: a value is followed, in brackets
// on the line below, by how it compares with the long-term normal for the
// same period. Totals (rainfall) are shown as a percentage of normal, e.g.
// "(85%)"; averages (e.g. temperature) as a signed difference in the
// visitor's units, e.g. "(+1.2)". Normals live in data/climate.js; any
// variable / statistic without normals there (e.g. wind) gets no comparison.

export const CLIMATE_IS_PLACEHOLDER = !!CLIMATE_NORMALS.placeholder;
export const CLIMATE_PAGE = "/reports/climate";

/** Descriptive metadata from data/climate.js (shown on the climate page). */
export const CLIMATE_META = {
    source: CLIMATE_NORMALS.source || "",
    period: CLIMATE_NORMALS.period || "",
    notes: CLIMATE_NORMALS.notes || [],
};

const MONTHLY_KEYS = Array.from(Array(12).keys());

function mean(values) {
    return values.reduce((a, b) => a + b, 0) / values.length;
}

function isTotal(stat) {
    return stat === "total";
}

// Normalised normals entry for a variable + daily statistic, or null.
function normalsFor(obs, stat) {
    const byVar = CLIMATE_NORMALS.normals[obs];
    if (!byVar) {
        return null;
    }
    let entry = byVar[stat];
    if (!entry && obs === "temp" && stat === "avg" && byVar.min && byVar.max) {
        // Normal daily mean = mid-point of normal low and high (NOAA convention).
        entry = { monthly: MONTHLY_KEYS.map((m) => (byVar.min.monthly[m] + byVar.max.monthly[m]) / 2) };
    }
    if (!entry && obs === "sunpct" && stat === "avg") {
        // Sunshine as % of possible: normal sunshine hours / possible (sunrise-sunset) hours.
        const sun = CLIMATE_NORMALS.normals.sun;
        if (sun?.total?.monthly && sun?.possible?.monthly) {
            entry = {
                monthly: MONTHLY_KEYS.map((m) => 100 * sun.total.monthly[m] / sun.possible.monthly[m]),
                annual: sun.total.annual && sun.possible.annual ? 100 * sun.total.annual / sun.possible.annual : undefined,
            };
        }
    }
    if (!entry || !Array.isArray(entry.monthly) || entry.monthly.length !== 12) {
        return null;
    }
    const derivedAnnual = isTotal(stat)
        ? entry.monthly.reduce((a, b) => a + b, 0)
        : mean(entry.monthly);
    return {
        monthly: entry.monthly,
        annual: entry.annual ?? derivedAnnual,
        waterYear: entry.waterYear ?? (isTotal(stat) ? derivedAnnual : null),
    };
}

export function hasClimate(obs, stat) {
    return normalsFor(obs, stat) != null;
}

/** All 12 monthly normals (Jan..Dec), or null if there are none. */
export function monthlyNormals(obs, stat) {
    return normalsFor(obs, stat)?.monthly ?? null;
}

/** Normal for calendar month `month` (1-12). */
export function monthlyNormal(obs, stat, month) {
    return normalsFor(obs, stat)?.monthly[month - 1] ?? null;
}

/** Seasonal normal: sum of monthly totals, or mean of monthly means. Winter uses Dec+Jan+Feb. */
export function seasonalNormal(obs, stat, season) {
    const months = seasonMonths(season);
    if (!months.length) {
        return null;
    }
    const vals = months.map((m) => monthlyNormal(obs, stat, m));
    if (vals.some((v) => v == null)) {
        return null;
    }
    const total = vals.reduce((a, b) => a + b, 0);
    return isTotal(stat) ? total : total / vals.length;
}

export function annualNormal(obs, stat) {
    return normalsFor(obs, stat)?.annual ?? null;
}

/** Oct-Sep water-year normal (rain only). */
export function waterYearNormal(obs, stat) {
    return normalsFor(obs, stat)?.waterYear ?? null;
}

function daysInMonth(year, month) {
    return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

// First month of the Oct-Sep water year (kept in step with
// WATER_YEAR_START_MONTH in waterYear.js; not imported to avoid a cycle).
const WATER_YEAR_FIRST_MONTH = 10;

/**
 * Normal total expected by the end of `day` of `month`: the month's
 * normal x (day / days in month). Totals only (rain/sun); null for
 * variables without monthly normals.
 */
export function monthlyNormalToDate(obs, stat, year, month, day) {
    const entry = normalsFor(obs, stat);
    if (!entry || !isTotal(stat)) {
        return null;
    }
    return entry.monthly[month - 1] * (day / daysInMonth(year, month));
}

/**
 * Normal total expected by the end of `day` of `month` in the water year
 * containing that date: the monthly normals of the water year's completed
 * months, plus the current month's normal to date (same pro-rata as
 * monthlyNormalToDate). Totals only (rain); null for variables without
 * monthly normals.
 */
export function waterYearNormalToDate(obs, stat, year, month, day) {
    const entry = normalsFor(obs, stat);
    if (!entry || !isTotal(stat)) {
        return null;
    }
    const current = monthlyNormalToDate(obs, stat, year, month, day);
    if (current == null) {
        return null;
    }
    let expected = 0;
    for (let m = WATER_YEAR_FIRST_MONTH; m !== month; m = m % 12 + 1) {
        expected += entry.monthly[m - 1];
    }
    return expected + current;
}

/**
 * Date in the water year containing (year, month, day) at which the
 * cumulative 1991-2020 daily normal (same basis as waterYearNormalToDate)
 * first reaches `total`.
 *
 * Returns { month, day } (month 1-12). A zero total is the start of the
 * water year (1 Oct). If `total` is above the full-year normal, returns
 * { exceeds: true }. Null when the total or normals are missing.
 */
/**
 * Whole calendar days from (y0, m0, d0) to (y1, m1, d1). Station-local dates
 * compared as civil dates (UTC midnight arithmetic, so DST does not matter).
 */
export function calendarDaysBetween(y1, m1, d1, y0, m0, d0) {
    if ([y1, m1, d1, y0, m0, d0].some((v) => v == null || Number.isNaN(v))) {
        return null;
    }
    return Math.round((Date.UTC(y1, m1 - 1, d1) - Date.UTC(y0, m0 - 1, d0)) / 86400000);
}

/** "(+22 days)", "(-3 days)", "(+1 day)", or "(normal)" for a zero offset. */
export function waterYearDaysLabel(days) {
    if (days == null || Number.isNaN(days)) {
        return null;
    }
    if (days === 0) {
        return "(normal)";
    }
    const n = Math.abs(days);
    return "(" + (days > 0 ? "+" : "-") + n + " " + (n === 1 ? "day" : "days") + ")";
}

export function waterYearDateForTotal(obs, stat, year, month, day, total) {
    if (total == null || Number.isNaN(total) || total < 0) {
        return null;
    }
    if (waterYearNormalToDate(obs, stat, year, month, day) == null) {
        return null;
    }
    const startYear = month >= WATER_YEAR_FIRST_MONTH ? year : year - 1;
    if (total === 0) {
        return {
            month: WATER_YEAR_FIRST_MONTH, day: 1, year: startYear,
            days: calendarDaysBetween(startYear, WATER_YEAR_FIRST_MONTH, 1, year, month, day),
        };
    }
    const full = waterYearNormalToDate(obs, stat, startYear + 1, 9, 30);
    if (full == null) {
        return null;
    }
    if (total > full + 1e-9) {
        return { exceeds: true };
    }
    let y = startYear, m = WATER_YEAR_FIRST_MONTH, d = 1;
    const endY = startYear + 1;
    for (;;) {
        const expected = waterYearNormalToDate(obs, stat, y, m, d);
        if (expected != null && expected >= total) {
            return {
                month: m, day: d, year: y,
                days: calendarDaysBetween(y, m, d, year, month, day),
            };
        }
        d += 1;
        if (d > daysInMonth(y, m)) {
            d = 1;
            m += 1;
        }
        if (m > 12) {
            m = 1;
            y += 1;
        }
        if (y > endY || (y === endY && m === 10)) {
            break;
        }
    }
    return {
        month: 9, day: 30, year: startYear + 1,
        days: calendarDaysBetween(startYear + 1, 9, 30, year, month, day),
    };
}

/**
 * Normal for a single day. Totals: the month's normal spread evenly over its
 * days. Averages: linear interpolation between mid-month normals, so values
 * change smoothly across month boundaries.
 */
export function dailyNormal(obs, stat, year, month, day) {
    const entry = normalsFor(obs, stat);
    if (!entry) {
        return null;
    }
    if (isTotal(stat)) {
        return entry.monthly[month - 1] / daysInMonth(year, month);
    }
    const t = Date.UTC(year, month - 1, day);
    const midOf = (y, m) => Date.UTC(y, m - 1, 1) + (daysInMonth(y, m) / 2) * 86400000;
    let y0 = year, m0 = month;
    if (t < midOf(year, month)) {
        m0 = month - 1;
        if (m0 === 0) { m0 = 12; y0 = year - 1; }
    }
    let y1 = y0, m1 = m0 + 1;
    if (m1 === 13) { m1 = 1; y1 = y0 + 1; }
    const t0 = midOf(y0, m0), t1 = midOf(y1, m1);
    const f = (t - t0) / (t1 - t0);
    return entry.monthly[m0 - 1] + f * (entry.monthly[m1 - 1] - entry.monthly[m0 - 1]);
}

/**
 * dailyNormal() for every day of `year` (365 or 366 entries), as
 * { month, day, value } with month 1-12. Null if there are no normals.
 */
export function dailyNormalsForYear(obs, stat, year) {
    if (!hasClimate(obs, stat)) {
        return null;
    }
    const days = [];
    for (let month = 1; month <= 12; month++) {
        for (let day = 1; day <= daysInMonth(year, month); day++) {
            days.push({ month, day, value: dailyNormal(obs, stat, year, month, day) });
        }
    }
    return days;
}

/**
 * Comparison text (without brackets) for `value` against `normal`, or null.
 * Totals: percent of normal ("85%"); averages: signed difference in the
 * visitor's units ("+1.2", "-0.4").
 */
export function climateComparison(value, normal, obs, stat, unit) {
    if (value == null || normal == null || Number.isNaN(value)) {
        return null;
    }
    if (isTotal(stat)) {
        if (!(normal > 0)) {
            return null;
        }
        return Math.round((value / normal) * 100) + "%";
    }
    const fmat = OBS.get(obs).fmat === "temp" ? "abs_temp" : OBS.get(obs).fmat;
    const text = formatObs(unit, value - normal, fmat, true, false);
    return text.replace(/^-(0\.?0*)$/, "+$1");
}

/** "(+1.2)" / "(85%)" on its own line under a value, in the cell's colour. */

/**
 * Mean of daily temperature normals (min/max/avg) from startDate through endDate inclusive.
 * Used for in-progress month/year cards (elapsed days only).
 */
export function periodToDateTempNormal(stat, startYear, startMonth, startDay, endYear, endMonth, endDay) {
    if (!hasClimate("temp", stat)) return null;
    let sum = 0, n = 0;
    let y = startYear, m = startMonth, d = startDay;
    const end = Date.UTC(endYear, endMonth - 1, endDay);
    while (Date.UTC(y, m - 1, d) <= end) {
        const v = dailyNormal("temp", stat, y, m, d);
        if (v != null) { sum += v; n += 1; }
        d += 1;
        if (d > daysInMonth(y, m)) { d = 1; m += 1; }
        if (m > 12) { m = 1; y += 1; }
    }
    return n ? sum / n : null;
}

/**
 * Sum of daily normals for a total (rain/sun) from start through end inclusive (pro-rata to-date).
 */
export function periodToDateTotalNormal(obs, startYear, startMonth, startDay, endYear, endMonth, endDay) {
    if (!hasClimate(obs, "total")) return null;
    let sum = 0;
    let y = startYear, m = startMonth, d = startDay;
    const end = Date.UTC(endYear, endMonth - 1, endDay);
    while (Date.UTC(y, m - 1, d) <= end) {
        const v = dailyNormal(obs, "total", y, m, d);
        if (v != null) sum += v;
        d += 1;
        if (d > daysInMonth(y, m)) { d = 1; m += 1; }
        if (m > 12) { m = 1; y += 1; }
    }
    return sum;
}

/** Signed % departure from normal, e.g. "+12%" / "-5%". Null if unknown. */
export function signedPctDeparture(value, normal) {
    if (value == null || normal == null || !(normal > 0) || Number.isNaN(value)) return null;
    const pct = Math.round(((value / normal) - 1) * 100);
    return (pct > 0 ? "+" : "") + pct + "%";
}

export function ClimateAnom({ value, normal, obs, stat, unit, inline = false }) {
    const text = climateComparison(value, normal, obs, stat, unit);
    if (text == null) {
        return null;
    }
    return <Text as="span" className="climate-anom" display={inline ? "inline" : "block"} fontSize="sm"
        lineHeight="short" ml={inline ? "1" : undefined} fontWeight="normal"
        title={CLIMATE_IS_PLACEHOLDER ? "Compared with PLACEHOLDER climate normals" : "Compared with the climate normal"}>
        ({text})
    </Text>;
}

/** Footnote explaining bracketed figures (and flagging placeholder normals). */
export function ClimateNote({ currentPeriodNote = true, ...props }) {
    return <Text mt="2" className="climate-note" {...props}>
        Figures in brackets compare with the {CLIMATE_NORMALS.period}{" "}
        <ChakraLink href={CLIMATE_PAGE} color="inherit" textDecoration="underline">climate normal</ChakraLink>
        {" "}for the same period: the difference for temperature, and the percentage of normal for rainfall.
        {currentPeriodNote && " The comparison for the current month and year is not adjusted for how much of the period has passed."}
        {CLIMATE_IS_PLACEHOLDER && <Text as="span" fontWeight="bold" color="red.600">
            {" "}Climate normals are currently placeholders, not real averages.
        </Text>}
    </Text>;
}

/** Small "Climate normals" link shown under the heading of each report page. */
export function ClimateNormalsLink(props) {
    return <Text className="climate-normals-link" fontSize="sm" mt="-1" mb="2" {...props}>
        <NextLink href={CLIMATE_PAGE} passHref>
            <ChakraLink>Climate normals{CLIMATE_NORMALS.period && " (" + CLIMATE_NORMALS.period + ")"}</ChakraLink>
        </NextLink>
    </Text>;
}
