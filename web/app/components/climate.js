import { Text } from "@chakra-ui/react";
import { CLIMATE_NORMALS } from "../data/climate";
import { formatObs } from "../format";
import { OBS } from "./conf";

// Climate comparison, modelled on nw3weather: a value is followed, in brackets
// on the line below, by how it compares with the long-term normal for the
// same period. Totals (rainfall) are shown as a percentage of normal, e.g.
// "(85%)"; averages (temperature, wind) as a signed difference in the
// visitor's units, e.g. "(+1.2)". Normals live in data/climate.js.

export const CLIMATE_IS_PLACEHOLDER = !!CLIMATE_NORMALS.placeholder;

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

/** Normal for calendar month `month` (1-12). */
export function monthlyNormal(obs, stat, month) {
    return normalsFor(obs, stat)?.monthly[month - 1] ?? null;
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
export function ClimateAnom({ value, normal, obs, stat, unit }) {
    const text = climateComparison(value, normal, obs, stat, unit);
    if (text == null) {
        return null;
    }
    return <Text as="span" className="climate-anom" display="block" fontSize="sm" lineHeight="short"
        title={CLIMATE_IS_PLACEHOLDER ? "Compared with PLACEHOLDER climate normals" : "Compared with the climate normal"}>
        ({text})
    </Text>;
}

/** Footnote explaining bracketed figures (and flagging placeholder normals). */
export function ClimateNote({ currentPeriodNote = true, ...props }) {
    return <Text mt="2" className="climate-note" {...props}>
        Figures in brackets compare with the long-term climate normal for the same period: the difference
        for temperature and wind, and the percentage of normal for rainfall.
        {currentPeriodNote && " The comparison for the current month and year is not adjusted for how much of the period has passed."}
        {CLIMATE_IS_PLACEHOLDER && <Text as="span" fontWeight="bold" color="red.600">
            {" "}Climate normals are currently placeholders, not real averages.
        </Text>}
    </Text>;
}
