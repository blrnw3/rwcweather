import {
    Box,
    Heading,
    Link as ChakraLink,
    Spinner,
    Table,
    Tbody,
    Td,
    Text,
    Th,
    Thead,
    Tr,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useContext, useEffect } from "react";
import useSWR from "swr";
import { baseObs, defaultDailyStat, fetcher, fmatForObs, fmatObsOpt, isTotalObs, OBS } from "../../components/conf";
import { ClimateNormalsLink } from "../../components/climate";
import { Page, UnitCtx } from "../../components/Page";
import { inList, useUrlState } from "../../components/urlState";
import {
    cToF,
    countThresholdsAny,
    CountThresholdSelector,
    DAILY_AGGREGATION_NAMES,
    dailyAggregationOptions,
    inHgToMb,
    kphToMph,
    mmToIn,
    nearestThreshold,
    RadioButtonGroup,
    DAILY_VALUE_OBS_OPTIONS,
    DAILY_VALUE_OBS_STATES,
    MULTIDAY_OBS_STATES,
    REPORT_YEAR_START,
    SUMMARY_NAMES,
    summaryKey,
    summaryOptions,
    styleForReportValue,
    SunViewToggle,
} from "../../components/report";
import { formatObs } from "../../format";
import { hasWaterYears, useWaterYears, waterYearLabel, waterYearRange } from "../../components/waterYear";

const PERIOD_NAMES = {
    daily: "Daily",
    rolling: "Multi-day",
    spells: "Spells",
    anom: "Heat / cold",
    monthly: "Monthly",
    annual: "Annual",
    wateryear: "Water year",
};

// Periods built by summarising daily values (all but "daily" itself).
const SUMMARY_PERIODS = ["monthly", "annual", "wateryear"];

// Multi-day periods: N consecutive days, ranked server-side from the daily
// table (see rwcwx/calc/rolling.py).
const ROLLING_OBS = MULTIDAY_OBS_STATES;
const ROLLING_DAYS = ["3", "5", "7", "14", "30"];
const MIN_COVERAGE = { 3: 3, 5: 5, 7: 7, 14: 13, 30: 27 };

// Spells: longest runs of consecutive days above (>=) or below (<) a threshold, ranked server-side
// (see rwcwx/calc/spells.py). Thresholds are in inches, °F or hours, mirroring SPELL_VARS there.
const SPELL_CONF = {
    rain: { total: ["0.01", "0.1", "0.25", "0.5", "1"] },
    wet: { total: ["1", "3", "6", "12"] },
    wetrate: { avg: ["0.02", "0.05", "0.1", "0.2"] },
    rain60: { max: ["0.05", "0.1", "0.25", "0.5"] },
    rain10: { max: ["0.02", "0.05", "0.1", "0.2"] },
    temp: {
        max: ["40", "50", "60", "70", "80", "90", "100"],
        min: ["32", "40", "45", "50", "55", "60"],
        avg: ["40", "50", "60", "70", "80"],
    },
    sun: { total: ["0.1", "1", "4", "8", "10", "12"] },
    sunpct: { avg: ["10", "25", "50", "75", "90"] },
    humi: {
        max: ["50", "60", "70", "80", "90", "95"],
        min: ["20", "30", "40", "50", "60", "70"],
        avg: ["30", "40", "50", "60", "70", "80", "90"],
    },
    dewpt: {
        max: ["32", "40", "50", "55", "60", "65"],
        min: ["25", "32", "40", "45", "50", "55"],
        avg: ["32", "40", "45", "50", "55", "60"],
    },
    aqi: {
        max: ["25", "50", "100", "150", "200"],
        min: ["10", "25", "50", "100"],
        avg: ["25", "50", "100", "150"],
    },
    wind: {
        max: ["5", "10", "15", "20", "25"],
        avg: ["2", "4", "6", "8", "10"],
        min: ["1", "2", "5"],
    },
    gust: {
        max: ["10", "15", "20", "25", "30", "40"],
        avg: ["4", "6", "8", "10", "15"],
        min: ["1", "2", "5"],
    },
    pres: {
        max: ["1005", "1010", "1015", "1020", "1025"],
        min: ["1005", "1010", "1015", "1020", "1025"],
        avg: ["1005", "1010", "1015", "1020", "1025"],
    },
};
// Metric users (uk & eu) get round Celsius and mm thresholds, stored as their °F / inch equivalents
// to match SPELL_VARS in rwcwx/calc/spells.py.
const SPELL_CONF_METRIC = {
    rain: { total: ["0.01", ...[2, 5, 10, 25].map(mmToIn)] },
    wetrate: { avg: [0.5, 1, 2, 5].map(mmToIn) },
    rain60: { max: [1, 2, 5, 10].map(mmToIn) },
    rain10: { max: [0.5, 1, 2, 5].map(mmToIn) },
    temp: {
        max: [10, 15, 20, 25, 30, 35, 40].map(cToF),
        min: [0, 5, 10, 15].map(cToF),
        avg: [5, 10, 15, 20, 25].map(cToF),
    },
    dewpt: {
        max: [0, 5, 10, 15, 20].map(cToF),
        min: [-5, 0, 5, 10, 15].map(cToF),
        avg: [0, 5, 10, 15, 20].map(cToF),
    },
};
const SPELL_CONF_EU = {
    wind: {
        max: [10, 15, 20, 30, 40].map(kphToMph),
        avg: [5, 10, 15, 20].map(kphToMph),
        min: [2, 5, 10].map(kphToMph),
    },
    gust: {
        max: [15, 25, 30, 40, 50, 60].map(kphToMph),
        avg: [5, 10, 15, 20, 25].map(kphToMph),
        min: [2, 5, 10].map(kphToMph),
    },
};
const SPELL_CONF_US = {
    pres: {
        max: [29.7, 29.8, 29.9, 30.0, 30.1, 30.2].map(inHgToMb),
        min: [29.7, 29.8, 29.9, 30.0, 30.1, 30.2].map(inHgToMb),
        avg: [29.7, 29.8, 29.9, 30.0, 30.1, 30.2].map(inHgToMb),
    },
};
const SPELL_OBS = Object.keys(SPELL_CONF);

// Heatwave / cold snap vs 1991-2020 daily climate normal (departure thresholds).
// US: °F; metric: round °C stored as °F equivalents (matching backend LEVELS).
const ANOM_LEVELS_F = ["3", "5", "8", "10"];
// Metric UI: exact °C options, passed to the API as °F equivalents (c * 9/5).
const ANOM_LEVELS_C_DEG = [2, 3, 5, 7, 10];
const ANOM_LEVELS_C = ANOM_LEVELS_C_DEG.map((c) => String(c * 9 / 5));
const ANOM_LEVELS_US = ANOM_LEVELS_F;
const ANOM_LEVELS_METRIC = ANOM_LEVELS_C;
const ANOM_ORDERS = ["length", "cum", "peak"];
const ANOM_ORDER_NAMES = { length: "Longest", cum: "Most cumulative", peak: "Biggest peak" };
const ANOM_DIR_NAMES = { above: "Heatwave (≥)", below: "Cold snap (≤ −)" };

function anomLevels(unit) {
    return unit === "us" ? ANOM_LEVELS_US : ANOM_LEVELS_METRIC;
}
function anomDefaultLevel(unit) {
    return unit === "us" ? "5" : String(3 * 9 / 5); // 5 °F or 3 °C
}
function formatAnomLevel(unit, level) {
    const n = Number(level);
    if (unit === "us") return n + " °F";
    // Prefer whole °C when this level is a metric option
    for (const c of ANOM_LEVELS_C_DEG) {
        if (Math.abs(n - c * 9 / 5) < 1e-6) return c + " °C";
    }
    return (n * 5 / 9).toFixed(1) + " °C";
}
function formatAnomDep(unit, depC) {
    if (depC == null || Number.isNaN(depC)) return "–";
    if (unit === "us") {
        const f = depC * 9 / 5;
        const s = (f >= 0 ? "+" : "") + f.toFixed(1);
        return s + " °F";
    }
    const s = (depC >= 0 ? "+" : "") + Number(depC).toFixed(1);
    return s + " °C";
}

// Opening defaults: wet days for rain, warm days for temperatures, sunny days for sunshine.
const SPELL_DEFAULTS = {
    rain: "0.01", wet: "1", wetrate: "0.05", rain60: "0.1", rain10: "0.05",
    max: "80", min: "50", avg: "60",
    sun: "10", sunpct: "75",
    humi: "70", dewpt: "50", aqi: "50", wind: "10", gust: "20", pres: "1015",
};
const DEFAULT_SPELL_DIR_NAMES = { above: "Above (≥)", below: "Below (<)" };
const SPELL_DIR_NAMES = {
    rain: { above: "Wet (≥)", below: "Dry (<)" },
    wet: { above: "Wet (≥)", below: "Mostly dry (<)" },
    temp: { above: "Above (≥)", below: "Below (<)" },
    sun: { above: "Sunny (≥)", below: "Dull (<)" },
    sunpct: { above: "Sunny (≥)", below: "Dull (<)" },
};
const DEFAULT_SPELL_TITLE_WORDS = { above: "high", below: "low" };
const SPELL_TITLE_WORDS = {
    rain: { above: "wet", below: "dry" },
    wet: { above: "wet", below: "mostly dry" },
    temp: { above: "warm", below: "cold" },
    sun: { above: "sunny", below: "dull" },
    sunpct: { above: "sunny", below: "dull" },
    humi: { above: "humid", below: "dry" },
    wind: { above: "windy", below: "calm" },
    gust: { above: "gusty", below: "calm" },
    aqi: { above: "polluted", below: "clean" },
};
const SPELL_STATUS = { today: ", so far", pending: ", may continue today", yesterday: ", to yesterday" };
const SPELL_START_YEARS = ["all", ...Array.from(Array(new Date().getFullYear() - 2021 + 1).keys()).map((i) => String(2021 + i))];

// Options shown for the unit preference ("uk" / "eu" = metric temperatures & rainfall; "eu" = kph wind).
function spellThresholds(obs, stat, unit = "us") {
    if (unit === "eu" && SPELL_CONF_EU[obs]?.[stat]) {
        return SPELL_CONF_EU[obs][stat];
    }
    if (unit !== "us" && SPELL_CONF_METRIC[obs]?.[stat]) {
        return SPELL_CONF_METRIC[obs][stat];
    }
    if (unit === "us" && SPELL_CONF_US[obs]?.[stat]) {
        return SPELL_CONF_US[obs][stat];
    }
    return SPELL_CONF[obs]?.[stat] || [];
}

// Every value the URL / API accepts: all unit systems' options.
function spellThresholdsAny(obs, stat) {
    return [...new Set([
        ...spellThresholds(obs, stat, "us"),
        ...spellThresholds(obs, stat, "uk"),
        ...spellThresholds(obs, stat, "eu"),
        ...(obs === "rain" ? [mmToIn(0.2)] : []),
    ])];
}

function spellDefaultThreshold(obs, stat) {
    const list = spellThresholds(obs, stat);
    const def = SPELL_DEFAULTS[obs === "temp" ? stat : obs];
    return list.includes(def) ? def : list[0];
}

// Thresholds are entered in °F / inches / hours; temperatures are stored (and formatted from) °C.
function formatThreshold(unit, obs, value, stat) {
    if (obs === "wet" || obs === "sun") {
        return value + " h";
    }
    const num = Number(value);
    if (obs === "rain" && (num === 0.01 || num === 0.0079) && unit !== "us") {
        return "0.2 mm";
    }
    if (obs === "temp" || obs === "dewpt") {
        // Whole degrees in the viewer's unit: 86 -> "30 °C" (metric) or "86 °F".
        return unit !== "us" ? Math.round((num - 32) * 5 / 9 * 10) / 10 + " °C" : num + " °F";
    }
    const fmat = fmatForObs(obs, stat);
    const raw = formatObs(unit, num, fmat);
    return unit === "us" && (fmat === "rain" || fmat === "wetrate" || fmat === "pres")
        ? raw
        : raw.replace(/\.0+(?=\s|$)/, "");
}

function periodOptions(obs) {
    return [
        "daily",
        ...(ROLLING_OBS.includes(obs) ? ["rolling"] : []),
        ...(SPELL_OBS.includes(obs) ? ["spells"] : []),
        ...(obs === "temp" ? ["anom"] : []),
        ...(MULTIDAY_OBS_STATES.includes(obs) ? ["monthly", "annual"] : []),
        ...(hasWaterYears(obs) ? ["wateryear"] : []),
    ];
}

// The driest N-day spells are all zero, so rain multi-day only ranks highest.
function orderOptions(obs, period) {
    return period === "rolling" && (obs === "rain" || obs === "wet") ? ["highest"] : ["highest", "lowest"];
}

const ORDER_NAMES = {
    highest: "Highest",
    lowest: "Lowest",
};

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const SEASON_NAMES = { spring: "Spring", summer: "Summer", autumn: "Autumn", winter: "Winter" };
const SEASON_MONTHS = { spring: [3, 4, 5], summer: [6, 7, 8], autumn: [9, 10, 11], winter: [12, 1, 2] };
const SEASON_OPTIONS = Object.keys(SEASON_NAMES);
const monthOptions = ["all", ...SEASON_OPTIONS, ...Array.from(Array(12).keys()).map((month) => (month + 1).toString())];

function formatMonthFilter(value) {
    if (value === "all") return "All";
    if (SEASON_NAMES[value]) return SEASON_NAMES[value];
    return monthNames[Number(value) - 1];
}

function matchesMonthFilter(monthNum, filter) {
    if (filter === "all") return true;
    if (SEASON_MONTHS[filter]) return SEASON_MONTHS[filter].includes(monthNum);
    return monthNum === Number(filter);
}

// Day-of-year window for daily rankings: window 10 = ±5 days around a centre MMDD in any year
// (11 calendar days). Expansion uses a leap-year calendar so 29 Feb works; year wrap is via Date math.
// Matches rwcwx/calc/day_window.py.
const DAY_WINDOW_OPTIONS = ["all", "10", "30"];
const DAY_WINDOW_RADIUS = { "10": 5, "30": 15 };
const DAY_WINDOW_NAMES = { all: "All days", "10": "±5 days", "30": "±15 days" };
const REF_LEAP = 2024; // only for expanding (month, day) ranges

function pad2(n) { return String(n).padStart(2, "0"); }
function formatMmdd(month, day) { return pad2(month) + pad2(day); }
function parseMmdd(mmdd) {
    if (!/^\d{4}$/.test(mmdd || "")) return null;
    const month = Number(mmdd.slice(0, 2)), day = Number(mmdd.slice(2));
    const dt = new Date(REF_LEAP, month - 1, day);
    if (dt.getFullYear() !== REF_LEAP || dt.getMonth() !== month - 1 || dt.getDate() !== day) return null;
    return [month, day];
}
function mmddToday(d = new Date()) { return formatMmdd(d.getMonth() + 1, d.getDate()); }
function daysInMonth(month) {
    return new Date(REF_LEAP, month, 0).getDate(); // month is 1-12; day 0 of next month
}
function mdSet(centreMonth, centreDay, radius) {
    const centre = new Date(REF_LEAP, centreMonth - 1, centreDay);
    const out = new Set();
    for (let d = -radius; d <= radius; d++) {
        const dt = new Date(centre);
        dt.setDate(centre.getDate() + d);
        out.add(formatMmdd(dt.getMonth() + 1, dt.getDate()));
    }
    return out;
}
function matchesDayWindow(month, day, centreMmdd, window) {
    const radius = DAY_WINDOW_RADIUS[window];
    const centre = parseMmdd(centreMmdd);
    if (radius == null || !centre) return true;
    return mdSet(centre[0], centre[1], radius).has(formatMmdd(month, day));
}
function formatCentreLabel(mmdd) {
    const p = parseMmdd(mmdd);
    if (!p) return mmdd;
    return monthNames[p[0] - 1] + " " + p[1];
}
function formatWindowSuffix(window, centre) {
    if (window === "all") return "";
    const r = DAY_WINDOW_RADIUS[window];
    return " around " + formatCentreLabel(centre) + " (±" + r + " days)";
}


function useRankingData(obs, dailyAggregation) {
    const url = "/api/var/all_periods/" + obs + "/" + dailyAggregation
        + "/?start=" + REPORT_YEAR_START + "0101&include_today=1";
    return useSWR(url, fetcher, { refreshInterval: 300000 });
}

function formatPeriod(period, dateParts) {
    if (period === "wateryear") {
        return waterYearLabel(dateParts[0]) + " (" + waterYearRange(dateParts[0]) + ")";
    }
    if (period === "annual") {
        return dateParts[0].toString();
    }
    if (period === "monthly") {
        return monthNames[dateParts[1] - 1] + " " + dateParts[0];
    }
    return monthNames[dateParts[1] - 1] + " " + dateParts[2] + ", " + dateParts[0];
}

function monthlyCountRecords(dailyResults, threshold) {
    const counts = new Map();
    for (const result of dailyResults) {
        const [year, month] = result.d;
        const key = year + "-" + month;
        if (!counts.has(key)) {
            counts.set(key, { date: [year, month], value: 0 });
        }
        if (result.val > threshold) {
            counts.get(key).value++;
        }
    }
    return Array.from(counts.values());
}

function annualCountRecords(dailyResults, threshold) {
    const counts = new Map();
    for (const result of dailyResults) {
        const year = result.d[0];
        counts.set(year, (counts.get(year) || 0) + (result.val > threshold ? 1 : 0));
    }
    return Array.from(counts, ([year, value]) => ({ date: [year], value }));
}

// Annual and water-year rankings only include complete years: an in-progress
// (or partially recorded) year would otherwise dominate the "lowest" rankings.
function annualRecords(results, server, summary, threshold) {
    const dailyResults = results.daily || [];
    const currentYear = server?.date?.[0];
    const dateNum = (d) => d[0] * 10000 + d[1] * 100 + d[2];
    const firstDate = dailyResults.reduce((first, r) => (
        first == null || dateNum(r.d) < dateNum(first) ? r.d : first
    ), null);
    const isComplete = (year) => year !== currentYear && firstDate != null
        && (firstDate[0] < year || (firstDate[1] === 1 && firstDate[2] === 1));
    const records = summary === "count"
        ? annualCountRecords(dailyResults, Number(threshold))
        : (results.yearly || []).map((result) => ({
            date: [result.m],
            value: result.summary[summaryKey(summary)],
        }));
    return records.filter((record) => isComplete(record.date[0]));
}

// The in-progress period matching the selected granularity (today, this month,
// this year, this water year), or null. It may not be in the ranked list itself
// (annual and water-year rankings only list complete years).
function currentRecord(results, server, period, summary, threshold, waterYears) {
    const today = server?.date;
    if (!today) {
        return null;
    }
    if (period === "daily") {
        const r = (results.daily || []).find((x) => x.d[0] === today[0] && x.d[1] === today[1] && x.d[2] === today[2]);
        return r ? { date: r.d, value: r.val } : null;
    }
    if (period === "monthly") {
        const records = summary === "count"
            ? monthlyCountRecords(results.daily || [], Number(threshold))
            : (results.monthly || []).map((r) => ({ date: r.m, value: r.summary[summaryKey(summary)] }));
        return records.find((r) => r.date[0] === today[0] && r.date[1] === today[1]) || null;
    }
    if (period === "annual") {
        if (summary === "count") {
            return annualCountRecords(results.daily || [], Number(threshold)).find((r) => r.date[0] === today[0]) || null;
        }
        const r = (results.yearly || []).find((x) => x.m === today[0] || x.m?.[0] === today[0]);
        return r ? { date: [today[0]], value: r.summary[summaryKey(summary)] } : null;
    }
    if (period === "wateryear" && waterYears?.waterYears) {
        const info = waterYears.waterYears.get(waterYears.currentWaterYear);
        return info ? { date: [waterYears.currentWaterYear], value: info.value } : null;
    }
    return null;
}

// Last day a period covers: highlights use the period end (capped at today).
function periodEnd(period, dateParts) {
    if (period === "wateryear") {
        return [dateParts[0], 9, 30];
    }
    if (period === "annual") {
        return [dateParts[0], 12, 31];
    }
    if (period === "monthly") {
        return [dateParts[0], dateParts[1], new Date(Date.UTC(dateParts[0], dateParts[1], 0)).getUTCDate()];
    }
    return dateParts;
}

const RECENT_MONTH_DAYS = 30;
const RECENT_YEAR_DAYS = 365;

// "month" (ended in the last 30 days), "year" (last 365 days) or null.
export function recency(endParts, todayParts) {
    if (!endParts || !todayParts) {
        return null;
    }
    const utc = (d) => Date.UTC(d[0], d[1] - 1, d[2]);
    const ago = Math.max(0, Math.round((utc(todayParts) - utc(endParts)) / 86400000));
    return ago <= RECENT_MONTH_DAYS ? "month" : ago <= RECENT_YEAR_DAYS ? "year" : null;
}

const RECENT_STYLE = {
    month: { bg: "orange.300", fontWeight: "bold" },
    year: { bg: "orange.100" },
};

// Rank of value among values, ties sharing the better rank (as in the table).
function rankOf(value, values, order) {
    const better = values.filter((v) => order === "highest" ? v > value : v < value).length;
    return better + 1;
}

function RecentLegend() {
    return <Text id="ranking-legend" mt="2" fontSize="sm">
        <Box as="span" display="inline-block" w="0.9em" h="0.9em" mr="1" verticalAlign="middle" bg={RECENT_STYLE.month.bg} />
        ended in the last 30 days
        <Box as="span" display="inline-block" w="0.9em" h="0.9em" ml="3" mr="1" verticalAlign="middle" bg={RECENT_STYLE.year.bg} borderWidth="1px" borderColor="orange.200" />
        ended in the last year
    </Text>;
}

const CURRENT_LABEL = {
    daily: "Today",
    monthly: "This month",
    annual: "This year",
    wateryear: "This water year",
};

function formatPtile(rank, of) {
    if (rank == null || !of || of <= 0) {
        return null;
    }
    const p = Math.max(0, Math.min(100, 100 * (of - rank + 0.5) / of));
    return p >= 10 ? String(Math.round(p)) : p.toPrecision(2);
}

function CurrentContext({ label, periodLabel, value, rank, of, inTop, soFar = true }) {
    const ptile = formatPtile(rank, of);
    return <Text id="ranking-current" mt="3" p="2" bg="blue.50" borderLeftWidth="4px" borderColor="blue.400">
        <b>{label}{soFar ? " so far" : ""}</b> ({periodLabel}): <b>{value}</b>
        {rank != null ? <>, rank <b>{rank}</b> of {of}{ptile != null ? ` (${ptile}%ile)` : ""}{inTop ? " (in the list below)" : ""}</> : null}
    </Text>;
}

function waterYearRecords(waterYears) {
    if (!waterYears) {
        return [];
    }
    return Array.from(waterYears.waterYears)
        .filter(([, info]) => info.status === "complete")
        .map(([waterYear, info]) => ({ date: [waterYear], value: info.value }));
}

function rankingRecords(results, server, period, summary, threshold, waterYears) {
    if (period === "daily") {
        return (results.daily || []).map((result) => ({ date: result.d, value: result.val }));
    }
    if (period === "annual") {
        return annualRecords(results, server, summary, threshold);
    }
    if (period === "wateryear") {
        return waterYearRecords(waterYears);
    }
    if (summary === "count") {
        return monthlyCountRecords(results.daily || [], Number(threshold));
    }
    const selectedSummaryKey = summaryKey(summary);
    return (results.monthly || []).map((result) => ({
        date: result.m,
        value: result.summary[selectedSummaryKey],
    }));
}

function isoDate(parts) {
    return parts.map((part, i) => i === 0 ? String(part) : String(part).padStart(2, "0")).join("-");
}

function formatSpan(start, end) {
    const short = (d) => monthNames[d[1] - 1] + " " + d[2];
    return start[0] === end[0]
        ? short(start) + " – " + short(end) + ", " + end[0]
        : short(start) + ", " + start[0] + " – " + short(end) + ", " + end[0];
}

function DayLink({ date, children }) {
    return <NextLink href={"/reports/day?date=" + isoDate(date)} passHref>
        <ChakraLink>{children}</ChakraLink>
    </NextLink>;
}

function RollingRankingTable({ obs, dailyAggregation, days, month, order, limit }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);
    const fmat = fmatForObs(obs, dailyAggregation);
    const url = "/api/var/rolling/" + obs + "/" + dailyAggregation + "/?days=" + days + "&order=" + order
        + "&month=" + (month === "all" ? 0 : month) + "&limit=" + limit;
    const { data: response, error, isValidating } = useSWR(url, fetcher, { refreshInterval: 300000 });

    if (error || response?.error) {
        return <Text mt="4" color="red.600">Unable to load ranking data.</Text>;
    }
    if (!response) {
        return <Box mt="5"><Spinner size="md" /> Loading rankings…</Box>;
    }
    const records = response.result || [];
    const today = response.server?.date;
    const current = response.current;
    const currentInTop = current && records.some((r) => r.end.join("-") === current.end.join("-"));
    const showCurrentRow = current && !currentInTop;
    let previousValue = null;
    let displayedRank = 0;

    return <Box mt="5" overflowX="auto" maxW="860px">
        {isValidating && <Text color="gray.500" fontSize="sm">Refreshing…</Text>}
        {current ? <CurrentContext
            label={"Latest " + days + " days"}
            periodLabel={formatSpan(current.start, current.end)}
            value={formatObs(unit, current.val, fmat)}
            rank={current.rank}
            of={current.of}
            inTop={currentInTop}
            soFar={today != null && current.end.join("-") === today.join("-")}
        /> : <Text mt="3" color="gray.500">The latest {days} days don&apos;t have enough data (or don&apos;t match the selected month/season) to rank.</Text>}
        <RecentLegend />
        <Table id="ranking-table" variant="simple" size="md">
            <Thead>
                <Tr>
                    <Th isNumeric>Rank</Th>
                    <Th>{days}-day period</Th>
                    <Th isNumeric>{obsObj.name} ({isTotalObs(obs) ? "total" : "mean"})</Th>
                </Tr>
            </Thead>
            <Tbody>
                {records.map((record, index) => {
                    if (record.val !== previousValue) {
                        displayedRank = index + 1;
                        previousValue = record.val;
                    }
                    const { bg, col } = styleForReportValue(record.val, fmat, unit, isTotalObs(obs) ? "total" : null);
                    const span = formatSpan(record.start, record.end);
                    const recent = recency(record.end, today);
                    const hl = recent ? RECENT_STYLE[recent] : {};
                    return <Tr key={record.end.join("-")} className={"rolling-row" + (recent ? " recent-" + recent : "")}>
                        <Td isNumeric fontWeight="bold" bg={hl.bg}>{displayedRank}</Td>
                        <Td bg={hl.bg} fontWeight={hl.fontWeight}>
                            <DayLink date={record.start}>{span.split(" – ")[0]}</DayLink>
                            {" – "}
                            <DayLink date={record.end}>{span.split(" – ")[1]}</DayLink>
                            {record.days < record.n && <Text as="span" color="gray.500" fontSize="sm">
                                {" "}({record.days} of {record.n} days with data)
                            </Text>}
                        </Td>
                        <Td isNumeric backgroundColor={bg} color={col}>{formatObs(unit, record.val, fmat)}</Td>
                    </Tr>;
                })}
                {showCurrentRow && <Tr id="ranking-current-row" borderTopWidth="3px" borderTopStyle="dashed">
                    <Td isNumeric fontWeight="bold" bg="blue.50">{current.rank}</Td>
                    <Td bg="blue.50">Latest {days} days: {formatSpan(current.start, current.end)}
                        {current.days < current.n && <Text as="span" color="gray.500" fontSize="sm">
                            {" "}({current.days} of {current.n} days with data)
                        </Text>}
                    </Td>
                    <Td isNumeric bg="blue.50">{formatObs(unit, current.val, fmat)}</Td>
                </Tr>}
            </Tbody>
        </Table>
        {records.length === 0 && <Text py="4">No ranking data is available.</Text>}
    </Box>;
}

// Inside <Page>, so they can read the unit preference.
function SpellTitle({ obs, dailyAggregation, dir, threshold, limit }) {
    const unit = useContext(UnitCtx);
    const words = SPELL_TITLE_WORDS[obs] || DEFAULT_SPELL_TITLE_WORDS;
    return <>Longest {limit} {words[dir]} spells
        ({DAILY_AGGREGATION_NAMES[dailyAggregation]} {dir === "above" ? "≥" : "<"} {formatThreshold(unit, obs, threshold, dailyAggregation)}) –</>;
}

function SpellThresholdSelector({ obs, dailyAggregation, value, fn }) {
    const unit = useContext(UnitCtx);
    const options = spellThresholds(obs, dailyAggregation, unit);
    const nearest = nearestThreshold(value, options);
    // A °F value in a metric view (or vice versa), e.g. from a shared link or after switching units:
    // move to the nearest option for this unit so a button is always selected.
    useEffect(() => {
        if (nearest !== value) {
            fn(nearest);
        }
    }, [nearest, value]);  // eslint-disable-line react-hooks/exhaustive-deps
    return <>
        <Text mt="1" fontWeight="bold">Threshold:</Text>
        <RadioButtonGroup name="level" value={value} options={options}
            optFormat={(v) => formatThreshold(unit, obs, v, dailyAggregation)} fn={fn} />
    </>;
}

function spanParts(record) {
    const span = formatSpan(record.start, record.end).split(" – ");
    return <>
        <DayLink date={record.start}>{span[0]}</DayLink>
        {" – "}
        <DayLink date={record.end}>{span[1]}</DayLink>
    </>;
}


function AnomTitle({ dailyAggregation, dir, level, limit, order }) {
    const unit = useContext(UnitCtx);
    const kind = dir === "above" ? "heatwave" : "cold snap";
    return <>{ANOM_ORDER_NAMES[order]} {limit} {kind}s
        ({DAILY_AGGREGATION_NAMES[dailyAggregation]} {dir === "above" ? "≥ +" : "≤ −"}{formatAnomLevel(unit, level).replace(" °", "°")} vs normal) –</>;
}

function AnomLevelSelector({ value, fn }) {
    const unit = useContext(UnitCtx);
    const options = anomLevels(unit);
    const nearest = nearestThreshold(value, options);
    useEffect(() => {
        if (nearest !== value) fn(nearest);
    }, [nearest, value]);  // eslint-disable-line react-hooks/exhaustive-deps
    return <>
        <Text mt="1" fontWeight="bold">Departure:</Text>
        <RadioButtonGroup name="level" value={value} options={options}
            optFormat={(v) => formatAnomLevel(unit, v)} fn={fn} />
    </>;
}

function AnomSpellRankingTable({ dailyAggregation, dir, level, order, month, limit }) {
    const unit = useContext(UnitCtx);
    const url = "/api/var/anom_spells/temp/" + dailyAggregation + "/?dir=" + dir + "&level=" + level
        + "&order=" + order + "&month=" + (month === "all" ? 0 : month) + "&limit=" + limit;
    const { data: response, error, isValidating } = useSWR(url, fetcher, { refreshInterval: 300000 });

    if (error || response?.error) {
        return <Text mt="4" color="red.600">Unable to load heat/cold spell data.</Text>;
    }
    if (!response) {
        return <Box mt="5"><Spinner size="md" /> Loading…</Box>;
    }
    const records = response.result || [];
    const today = response.server?.date;
    const current = response.current;
    const sameSpell = (r) => current && r.start.join("-") === current.start.join("-");
    const currentInTop = current && records.some(sameSpell);
    const days = (n) => n + (n === 1 ? " day" : " days");
    const curPtile = current ? formatPtile(current.rank, current.of) : null;
    let previousKey = null;
    let displayedRank = 0;
    const rankKey = (r) => order === "cum" ? r.cum : order === "peak" ? r.peak : r.length;

    return <Box mt="5" overflowX="auto" maxW="860px">
        {isValidating && <Text color="gray.500" fontSize="sm">Refreshing…</Text>}
        {current ? <Text id="ranking-current" mt="3" p="2" bg="blue.50" borderLeftWidth="4px" borderColor="blue.400">
            <b>Current spell</b> ({formatSpan(current.start, current.end)}, through yesterday):
            {" "}<b>{days(current.length)}</b>, mean {formatAnomDep(unit, current.mean)}, peak {formatAnomDep(unit, current.peak)},
            {" "}rank <b>{current.rank}</b> of {current.of}{curPtile != null ? ` (${curPtile}%ile)` : ""}{currentInTop ? " (in the list below)" : ""}
        </Text> : <Text mt="3" color="gray.500">No matching heat/cold spell is running (through yesterday).</Text>}
        <RecentLegend />
        <Table id="ranking-table" variant="simple" size="md">
            <Thead>
                <Tr>
                    <Th isNumeric>Rank</Th>
                    <Th isNumeric>Length</Th>
                    <Th>Period</Th>
                    <Th isNumeric>Mean dep.</Th>
                    <Th isNumeric>Peak dep.</Th>
                    <Th isNumeric>Cumulative</Th>
                </Tr>
            </Thead>
            <Tbody>
                {records.map((record, index) => {
                    const key = rankKey(record);
                    if (key !== previousKey) {
                        displayedRank = index + 1;
                        previousKey = key;
                    }
                    const recent = recency(record.end, today);
                    const hl = recent ? RECENT_STYLE[recent] : {};
                    const isCurrent = sameSpell(record);
                    return <Tr key={record.start.join("-") + "-" + record.end.join("-")} className={recent ? "recent-" + recent : undefined}
                        {...(isCurrent ? { bg: "blue.50" } : {})}>
                        <Td isNumeric fontWeight="bold" bg={hl.bg}>{displayedRank}</Td>
                        <Td isNumeric bg={hl.bg} fontWeight="bold">{days(record.length)}</Td>
                        <Td bg={hl.bg} fontWeight={hl.fontWeight}>{spanParts(record)}</Td>
                        <Td isNumeric>{formatAnomDep(unit, record.mean)}</Td>
                        <Td isNumeric>{formatAnomDep(unit, record.peak)}</Td>
                        <Td isNumeric>{formatAnomDep(unit, record.cum)}</Td>
                    </Tr>;
                })}
                {current && !currentInTop && <Tr id="ranking-current-row" borderTopWidth="3px" borderTopStyle="dashed">
                    <Td isNumeric fontWeight="bold" bg="blue.50">{current.rank}</Td>
                    <Td isNumeric bg="blue.50" fontWeight="bold">{days(current.length)}</Td>
                    <Td bg="blue.50">Current: {spanParts(current)}</Td>
                    <Td isNumeric bg="blue.50">{formatAnomDep(unit, current.mean)}</Td>
                    <Td isNumeric bg="blue.50">{formatAnomDep(unit, current.peak)}</Td>
                    <Td isNumeric bg="blue.50">{formatAnomDep(unit, current.cum)}</Td>
                </Tr>}
            </Tbody>
        </Table>
        <Text mt="2" fontSize="sm" color="gray.600">
            Found {response.found} matching spell{response.found === 1 ? "" : "s"}; showing the top {Math.min(records.length, Number(limit))}.
        </Text>
        {records.length === 0 && <Text py="4">No spells match this rule.</Text>}
    </Box>;
}

function SpellRankingTable({ obs, dailyAggregation, dir, threshold, month, startYear, limit }) {
    const unit = useContext(UnitCtx);
    const fmat = fmatForObs(obs, dailyAggregation);
    const url = "/api/var/spells/" + obs + "/" + dailyAggregation + "/?dir=" + dir + "&threshold=" + threshold
        + "&month=" + (month === "all" ? 0 : month) + (startYear === "all" ? "" : "&start_year=" + startYear) + "&limit=" + limit;
    const { data: response, error, isValidating } = useSWR(url, fetcher, { refreshInterval: 300000 });

    if (error || response?.error) {
        return <Text mt="4" color="red.600">Unable to load spell data.</Text>;
    }
    if (!response) {
        return <Box mt="5"><Spinner size="md" /> Loading spells…</Box>;
    }
    const records = response.result || [];
    const today = response.server?.date;
    const current = response.current;
    const sameSpell = (r) => current && r.start.join("-") === current.start.join("-");
    const currentInTop = current && records.some(sameSpell);
    const isTotal = response.stat === "total";
    // e.g. dry spells (rain < 0.01 in) are all zero: the stats columns would say nothing.
    const showStats = records.some((r) => r.max !== 0) || (current && current.max !== 0);
    const fmt = (v) => formatObs(unit, v, fmat);
    const days = (n) => n + (n === 1 ? " day" : " days");
    const curPtile = current ? formatPtile(current.rank, current.of) : null;
    let previousLength = null;
    let displayedRank = 0;

    return <Box mt="5" overflowX="auto" maxW="860px">
        {isValidating && <Text color="gray.500" fontSize="sm">Refreshing…</Text>}
        {current ? <Text id="ranking-current" mt="3" p="2" bg="blue.50" borderLeftWidth="4px" borderColor="blue.400">
            <b>Current spell</b> ({formatSpan(current.start, current.end)}{SPELL_STATUS[current.status]}):
            {" "}<b>{days(current.length)}</b>, rank <b>{current.rank}</b> of {current.of}{curPtile != null ? ` (${curPtile}%ile)` : ""}{currentInTop ? " (in the list below)" : ""}
        </Text> : <Text mt="3" color="gray.500">No spell matching this rule is running now.</Text>}
        <RecentLegend />
        <Table id="ranking-table" variant="simple" size="md">
            <Thead>
                <Tr>
                    <Th isNumeric>Rank</Th>
                    <Th isNumeric>Length</Th>
                    <Th>Period</Th>
                    {showStats && <>
                        {isTotal && <Th isNumeric>Total</Th>}
                        <Th isNumeric>Mean</Th>
                        <Th isNumeric>Min</Th>
                        <Th isNumeric>Max</Th>
                    </>}
                </Tr>
            </Thead>
            <Tbody>
                {records.map((record, index) => {
                    if (record.length !== previousLength) {
                        displayedRank = index + 1;
                        previousLength = record.length;
                    }
                    const ongoing = sameSpell(record);
                    const recent = ongoing ? "month" : recency(record.end, today);
                    const hl = recent ? RECENT_STYLE[recent] : {};
                    return <Tr key={record.start.join("-")} className={"spell-row" + (recent ? " recent-" + recent : "") + (ongoing ? " ongoing" : "")}>
                        <Td isNumeric fontWeight="bold" bg={hl.bg}>{displayedRank}</Td>
                        <Td isNumeric bg={hl.bg} fontWeight="bold">{days(record.length)}</Td>
                        <Td bg={hl.bg} fontWeight={hl.fontWeight}>
                            {spanParts(record)}
                            {ongoing && <Text as="span" color="blue.700" fontSize="sm"> (ongoing)</Text>}
                        </Td>
                        {showStats && <>
                            {isTotal && <Td isNumeric>{fmt(record.total)}</Td>}
                            <Td isNumeric>{fmt(record.mean)}</Td>
                            <Td isNumeric>{fmt(record.min)}</Td>
                            <Td isNumeric>{fmt(record.max)}</Td>
                        </>}
                    </Tr>;
                })}
                {current && !currentInTop && <Tr id="ranking-current-row" borderTopWidth="3px" borderTopStyle="dashed">
                    <Td isNumeric fontWeight="bold" bg="blue.50">{current.rank}</Td>
                    <Td isNumeric bg="blue.50" fontWeight="bold">{days(current.length)}</Td>
                    <Td bg="blue.50">Current spell: {spanParts(current)}</Td>
                    {showStats && <>
                        {isTotal && <Td isNumeric bg="blue.50">{fmt(current.total)}</Td>}
                        <Td isNumeric bg="blue.50">{fmt(current.mean)}</Td>
                        <Td isNumeric bg="blue.50">{fmt(current.min)}</Td>
                        <Td isNumeric bg="blue.50">{fmt(current.max)}</Td>
                    </>}
                </Tr>}
            </Tbody>
        </Table>
        <Text mt="2" fontSize="sm" color="gray.600">
            Found {response.found} matching spell{response.found === 1 ? "" : "s"}; showing the longest {Math.min(records.length, Number(limit))}.
        </Text>
        {records.length === 0 && <Text py="4">No spells match this rule.</Text>}
    </Box>;
}

function RankingTable({ obs, dailyAggregation, period, summary, threshold, month, window = "all", centre, order, limit }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);
    const fmat = fmatForObs(obs, dailyAggregation);
    const { data: response, error, isValidating } = useRankingData(obs, dailyAggregation);
    const waterYears = useWaterYears(period === "wateryear" ? obs : null, summary, threshold);
    const results = response?.result || {};
    const isSummaryPeriod = SUMMARY_PERIODS.includes(period);
    const byMonth = period === "daily" || period === "monthly";
    const useDayWindow = period === "daily" && window !== "all";
    const allRecords = rankingRecords(results, response?.server, period, summary, threshold, waterYears)
        .filter((record) => Number.isFinite(record.value))
        .filter((record) => {
            if (useDayWindow) return matchesDayWindow(record.date[1], record.date[2], centre, window);
            return !byMonth || matchesMonthFilter(record.date[1], month);
        })
        .sort((a, b) => {
            const valueOrder = order === "highest" ? b.value - a.value : a.value - b.value;
            if (valueOrder !== 0) {
                return valueOrder;
            }
            return b.date.join("-").localeCompare(a.date.join("-"));
        });
    const records = allRecords.slice(0, Number(limit));
    const today = response?.server?.date;

    // Current period context: computed from the rows already loaded for the ranking (no extra request).
    const current = currentRecord(results, response?.server, period, summary, threshold, waterYears);
    const currentKey = current?.date.join("-");
    const currentInList = current != null && allRecords.some((r) => r.date.join("-") === currentKey);
    const currentInTop = current != null && records.some((r) => r.date.join("-") === currentKey);
    const currentMonthExcluded = !useDayWindow && byMonth && month !== "all" && today && !matchesMonthFilter(today[1], month);
    const currentWindowExcluded = useDayWindow && today && !matchesDayWindow(today[1], today[2], centre, window);
    const currentExcluded = currentMonthExcluded || currentWindowExcluded;
    const currentRanked = current != null && Number.isFinite(current.value) && !currentExcluded;
    const otherValues = allRecords.filter((r) => r.date.join("-") !== currentKey).map((r) => r.value);
    const currentRank = currentRanked ? rankOf(current.value, otherValues, order) : null;
    const currentOf = otherValues.length + 1;
    const fmtValue = (value) => summary === "count" && isSummaryPeriod
        ? value.toString()
        : formatObs(unit, value, fmat);
    const currentPeriodLabel = current
        ? (period === "wateryear" ? waterYearLabel(current.date[0]) : formatPeriod(period, current.date))
        : null;

    if (error || waterYears?.error) {
        return <Text mt="4" color="red.600">Unable to load ranking data.</Text>;
    }
    if (!response || (waterYears && !waterYears.response)) {
        return <Box mt="5"><Spinner size="md" /> Loading rankings…</Box>;
    }

    let previousValue = null;
    let displayedRank = 0;

    return <Box mt="5" overflowX="auto" maxW="860px">
        {isValidating && <Text color="gray.500" fontSize="sm">Refreshing…</Text>}
        {currentRanked ? <CurrentContext
            label={CURRENT_LABEL[period]}
            periodLabel={currentPeriodLabel}
            value={fmtValue(current.value)}
            rank={currentRank}
            of={currentOf}
            inTop={currentInTop}
        /> : <Text id="ranking-current" mt="3" color="gray.500">
            {currentWindowExcluded
                ? CURRENT_LABEL[period] + " isn't in the " + formatCentreLabel(centre)
                    + " ±" + DAY_WINDOW_RADIUS[window] + "-day window; choose All days or move the centre to see how it ranks."
                : currentMonthExcluded
                ? CURRENT_LABEL[period] + " isn't in " + formatMonthFilter(month) + "; choose All or "
                    + monthNames[today[1] - 1] + " to see how it ranks."
                : "No data yet for " + CURRENT_LABEL[period].toLowerCase() + "."}
        </Text>}
        {!currentInList && currentRanked && period !== "daily" && period !== "monthly" && <Text fontSize="sm" color="gray.500">
            In-progress years aren't listed; the rank shows where the total so far would sit among complete years.
        </Text>}
        <RecentLegend />
        <Table id="ranking-table" variant="simple" size="md">
            <Thead>
                <Tr>
                    <Th isNumeric>Rank</Th>
                    <Th>{{ daily: "Date", monthly: "Month", annual: "Year", wateryear: "Water year" }[period]}</Th>
                    <Th isNumeric>{summary === "count" && isSummaryPeriod ? "Days" : obsObj.name}</Th>
                </Tr>
            </Thead>
            <Tbody>
                {records.map((record, index) => {
                    if (record.value !== previousValue) {
                        displayedRank = index + 1;
                        previousValue = record.value;
                    }
                    const formattedValue = summary === "count" && isSummaryPeriod
                        ? record.value.toString()
                        : formatObs(unit, record.value, fmat);
                    const selectedSummary = isSummaryPeriod ? summary : null;
                    const { bg, col } = styleForReportValue(
                        record.value, fmat, unit, selectedSummary, period === "annual" || period === "wateryear", isSummaryPeriod
                    );

                    const recent = recency(periodEnd(period, record.date), today);
                    const hl = recent ? RECENT_STYLE[recent] : {};
                    const isCurrent = record.date.join("-") === currentKey;
                    return <Tr key={record.date.join("-")} className={recent ? "recent-" + recent : undefined}>
                        <Td isNumeric fontWeight="bold" bg={hl.bg}>{displayedRank}</Td>
                        <Td bg={hl.bg} fontWeight={hl.fontWeight}>
                            {period === "daily" ? <DayLink date={record.date}>{formatPeriod(period, record.date)}</DayLink>
                                : formatPeriod(period, record.date)}
                            {isCurrent && <Text as="span" color="gray.600" fontSize="sm"> (so far)</Text>}
                        </Td>
                        <Td isNumeric backgroundColor={bg} color={col}>{formattedValue}</Td>
                    </Tr>;
                })}
                {currentRanked && !currentInTop && <Tr id="ranking-current-row" borderTopWidth="3px" borderTopStyle="dashed">
                    <Td isNumeric fontWeight="bold" bg="blue.50">{currentRank}</Td>
                    <Td bg="blue.50">{CURRENT_LABEL[period]}: {currentPeriodLabel}
                        <Text as="span" color="gray.600" fontSize="sm"> (so far)</Text></Td>
                    <Td isNumeric bg="blue.50">{fmtValue(current.value)}</Td>
                </Tr>}
            </Tbody>
        </Table>
        {records.length === 0 && <Text py="4">No ranking data is available.</Text>}
    </Box>;
}

const monthParam = (value) => value === "all" || SEASON_NAMES[value] ? value : monthNames[Number(value) - 1].toLowerCase();
const monthFromParam = (value) => {
    const low = String(value).toLowerCase();
    if (SEASON_NAMES[low]) {
        return low;
    }
    const index = monthNames.findIndex((name) => name.toLowerCase() === low);
    return index >= 0 ? (index + 1).toString() : value;
};

// Selections kept in the URL, e.g. /reports/ranking?var=rain&period=wateryear,
// /reports/ranking?var=rain&period=rolling&days=7
// or /reports/ranking?period=monthly&month=jul&order=lowest. Keys resolve in
// order, so the period can depend on the variable (water years: rain only).
const RANKING_URL_STATE = {
    obs: { param: "var", def: () => "temp", valid: inList(DAILY_VALUE_OBS_STATES) },
    period: { def: () => "daily", valid: (v, s) => periodOptions(s.obs).includes(v) },
    dailyAggregation: {
        param: "daily", def: (s) => defaultDailyStat(s.obs),
        valid: (v, s) => dailyAggregationOptions(s.obs).includes(v),
    },
    summary: {
        // Totals and the rain rate default to their period statistic (sum; rain / wet hours), not the max of daily values.
        def: (s) => isTotalObs(s.obs) || s.obs === "wetrate" ? OBS.get(s.obs).summary : "max",
        valid: (v, s) => summaryOptions(s.obs).includes(v),
        use: (s) => SUMMARY_PERIODS.includes(s.period),
    },
    threshold: {
        def: () => "0", valid: (v, s) => countThresholdsAny(s.obs).includes(v),
        use: (s) => SUMMARY_PERIODS.includes(s.period) && s.summary === "count",
    },
    window: {
        def: () => "all", valid: inList(DAY_WINDOW_OPTIONS),
        use: (s) => s.period === "daily",
    },
    centre: {
        def: () => mmddToday(), valid: (v) => parseMmdd(v) != null,
        use: (s) => s.period === "daily" && s.window !== "all",
    },
    month: {
        def: () => "all", valid: inList(monthOptions), toUrl: monthParam, fromUrl: monthFromParam,
        // Day window replaces month/season for daily (mutual exclusive); other periods keep month.
        use: (s) => (s.period === "daily" && s.window === "all")
            || s.period === "monthly" || s.period === "rolling" || s.period === "spells" || s.period === "anom",
    },
    dir: { def: () => "above", valid: inList(["above", "below"]), use: (s) => s.period === "spells" || s.period === "anom" },
    anomLevel: {
        param: "level", def: () => "5",
        valid: (v) => ANOM_LEVELS_METRIC.includes(v) || ANOM_LEVELS_US.includes(v),
        use: (s) => s.period === "anom",
    },
    anomOrder: {
        param: "rankby", def: () => "length", valid: inList(ANOM_ORDERS),
        use: (s) => s.period === "anom",
    },
    spellThreshold: {
        param: "level", def: (s) => spellDefaultThreshold(s.obs, s.dailyAggregation),
        valid: (v, s) => spellThresholdsAny(s.obs, s.dailyAggregation).includes(v),
        use: (s) => s.period === "spells",
    },
    startYear: { param: "from", def: () => "all", valid: inList(SPELL_START_YEARS), use: (s) => s.period === "spells" },
    days: { def: () => "3", valid: inList(ROLLING_DAYS), use: (s) => s.period === "rolling" },
    order: { def: () => "highest", valid: (v, s) => orderOptions(s.obs, s.period).includes(v) },
    limit: { param: "rows", def: () => "25", valid: inList(["10", "25", "50", "100"]) },
};

export default function RankingReport() {
    const [state, update] = useUrlState(RANKING_URL_STATE);
    const { period, obs, dailyAggregation, summary, threshold, month, window, centre, days, order, limit, dir, spellThreshold, startYear, anomLevel, anomOrder } = state;
    const dailyOptions = dailyAggregationOptions(obs);
    const monthlySummaryOptions = summaryOptions(obs);

    const handleObsChange = (nextObs, nextStat) => {
        const nextDaily = nextStat || (nextObs === "wind" ? "max" : defaultDailyStat(nextObs));
        update({
            obs: nextObs,
            dailyAggregation: nextDaily,
            threshold: "0",
            // Rain is mostly ranked by totals (wettest month / year / water year),
            // so switching to rain selects Total; other summaries stay selectable.
            summary: isTotalObs(nextObs) || summary === "avg" || summary === "total" ? OBS.get(nextObs).summary : summary,
            // Water years are rain-only; other variables fall back to calendar years.
            period: period === "wateryear" && !hasWaterYears(nextObs) ? "annual"
                : period === "rolling" && !ROLLING_OBS.includes(nextObs) ? "daily"
                : period === "spells" && !SPELL_OBS.includes(nextObs) ? "daily"
                : period === "anom" && nextObs !== "temp" ? "daily" : period,
            spellThreshold: spellDefaultThreshold(nextObs, nextDaily),
        });
    };

    const handlePeriodChange = (nextPeriod) => update({
        period: nextPeriod,
        ...(nextPeriod === "anom" && obs !== "temp" ? { obs: "temp", dailyAggregation: "max" } : {}),
        // Water years exist to compare rain totals, so open them on Total.
        ...(nextPeriod === "wateryear" && nextPeriod !== period ? { summary: OBS.get(obs).summary } : {}),
    });
    const setMonth = (value) => update({ month: value, window: "all" });
    const setWindow = (value) => update({
        window: value,
        ...(value !== "all" ? { month: "all", centre: parseMmdd(centre) ? centre : mmddToday() } : {}),
    });
    const setCentreMonth = (m) => {
        const max = daysInMonth(Number(m));
        const day = Math.min(Number((parseMmdd(centre) || [1, 1])[1]), max);
        update({ centre: formatMmdd(Number(m), day) });
    };
    const setCentreDay = (d) => {
        const monthNum = (parseMmdd(centre) || [1, 1])[0];
        update({ centre: formatMmdd(monthNum, Number(d)) });
    };
    const setDailyAggregation = (value) => update({
        dailyAggregation: value,
        ...(period === "spells" ? { spellThreshold: spellDefaultThreshold(obs, value) } : {}),
    });
    const setSummary = (value) => update({ summary: value });
    const setThreshold = (value) => update({ threshold: value });
    const setOrder = (value) => update({ order: value });
    const setDays = (value) => update({ days: value });
    const setDir = (value) => update({ dir: value });
    const setAnomLevel = (value) => update({ anomLevel: value });
    const setAnomOrder = (value) => update({ anomOrder: value });
    const setSpellThreshold = (value) => update({ spellThreshold: value });
    const setStartYear = (value) => update({ startYear: value });
    const setLimit = (value) => update({ limit: value });

    const isSummaryPeriod = SUMMARY_PERIODS.includes(period);
    const byMonth = period === "daily" || period === "monthly" || period === "rolling" || period === "spells" || period === "anom";
    const rankingTitle = period === "spells"
        ? <SpellTitle obs={obs} dailyAggregation={dailyAggregation} dir={dir} threshold={spellThreshold} limit={limit} />
        : period === "anom"
        ? <AnomTitle dailyAggregation={dailyAggregation} dir={dir} level={anomLevel} limit={limit} order={anomOrder} />
        : period === "daily"
        ? ORDER_NAMES[order] + " " + limit + " " + DAILY_AGGREGATION_NAMES[dailyAggregation]
        : period === "rolling"
        ? ORDER_NAMES[order] + " " + limit + " " + days + "-day " + (isTotalObs(obs) ? "totals" : "means")
            + " of " + DAILY_AGGREGATION_NAMES[dailyAggregation]
        : ORDER_NAMES[order] + " " + limit + " " + PERIOD_NAMES[period] + " " + SUMMARY_NAMES[summary]
            + " of " + DAILY_AGGREGATION_NAMES[dailyAggregation];
    const monthSuffix = period === "daily" && window !== "all"
        ? formatWindowSuffix(window, centre)
        : (!byMonth || month === "all" ? "" : " in " + formatMonthFilter(month));
    const dirNames = SPELL_DIR_NAMES[obs] || DEFAULT_SPELL_DIR_NAMES;

    return <Page name="reports" sub="ranking" title="Reports | rankings">
        <Heading as="h1" size="1">Reports: Rankings</Heading>
        <Heading as="h2" size="2">
            {rankingTitle} {OBS.get(obs).name}{monthSuffix}
        </Heading>
        <ClimateNormalsLink />

        <Text fontWeight="bold">Period:</Text>
        <RadioButtonGroup name="period" value={period} options={periodOptions(obs)} optFormat={(value) => PERIOD_NAMES[value]} fn={handlePeriodChange} />
        {period === "daily" && <>
            <Text mt="1" fontWeight="bold">Day window:</Text>
            <RadioButtonGroup name="window" value={window} options={DAY_WINDOW_OPTIONS} optFormat={(v) => DAY_WINDOW_NAMES[v]} fn={setWindow} />
            {window !== "all" && (() => {
                const parsed = parseMmdd(centre) || [new Date().getMonth() + 1, new Date().getDate()];
                const cMonth = parsed[0], cDay = parsed[1];
                const dayOpts = Array.from({ length: daysInMonth(cMonth) }, (_, i) => String(i + 1));
                return <>
                    <Text mt="1" fontWeight="bold">Centre date:</Text>
                    <RadioButtonGroup name="centre-month" value={String(cMonth)}
                        options={Array.from({ length: 12 }, (_, i) => String(i + 1))}
                        optFormat={(m) => monthNames[Number(m) - 1]} fn={setCentreMonth} />
                    <RadioButtonGroup name="centre-day" value={String(cDay)}
                        options={dayOpts} optFormat={(d) => d} fn={setCentreDay} />
                </>;
            })()}
        </>}
        {byMonth && (period !== "daily" || window === "all") && <>
            <Text mt="1" fontWeight="bold">Month / season:</Text>
            <RadioButtonGroup
                name="month"
                value={month}
                options={monthOptions}
                optFormat={formatMonthFilter}
                fn={setMonth}
            />
        </>}
        {period === "rolling" && <>
            <Text mt="1" fontWeight="bold">Length:</Text>
            <RadioButtonGroup name="days" value={days} options={ROLLING_DAYS} optFormat={(value) => value + " days"} fn={setDays} />
        </>}
        <Text mt="1" fontWeight="bold">Variable:</Text>
        <RadioButtonGroup name="obs" value={baseObs(obs)} options={DAILY_VALUE_OBS_OPTIONS} optFormat={fmatObsOpt} fn={handleObsChange} />
        <SunViewToggle obs={obs} stat={dailyAggregation} fn={handleObsChange} multiDay={period !== "daily"} />
        {baseObs(obs) !== "wind" && dailyOptions.length > 1 && <>
            <Text mt="1" fontWeight="bold">Daily statistic:</Text>
            <RadioButtonGroup name="daily-aggregation" value={dailyAggregation}
                options={period === "spells" ? dailyOptions.filter((o) => spellThresholds(obs, o).length) : dailyOptions} optFormat={(value) => DAILY_AGGREGATION_NAMES[value]} fn={setDailyAggregation} />
        </>}
        {isSummaryPeriod && <>
            <Text mt="1" fontWeight="bold">{PERIOD_NAMES[period]} summary:</Text>
            <RadioButtonGroup name="summary" value={summary} options={monthlySummaryOptions} optFormat={(value) => SUMMARY_NAMES[value]} fn={setSummary} />
            {summary === "count" && <CountThresholdSelector obs={obs} value={threshold} fn={setThreshold} />}
        </>}
        {period === "spells" ? <>
            <Text mt="1" fontWeight="bold">Spell:</Text>
            <RadioButtonGroup name="dir" value={dir} options={["above", "below"]} optFormat={(value) => dirNames[value]} fn={setDir} />
            <SpellThresholdSelector obs={obs} dailyAggregation={dailyAggregation} value={spellThreshold} fn={setSpellThreshold} />
            <Text mt="1" fontWeight="bold">From:</Text>
            <RadioButtonGroup name="from" value={startYear} options={SPELL_START_YEARS}
                optFormat={(value) => value === "all" ? "All years" : value} fn={setStartYear} />
        </> : period === "anom" ? <>
            <Text mt="1" fontWeight="bold">Type:</Text>
            <RadioButtonGroup name="dir" value={dir} options={["above", "below"]} optFormat={(value) => ANOM_DIR_NAMES[value]} fn={setDir} />
            <AnomLevelSelector value={anomLevel} fn={setAnomLevel} />
            <Text mt="1" fontWeight="bold">Rank by:</Text>
            <RadioButtonGroup name="rankby" value={anomOrder} options={ANOM_ORDERS} optFormat={(v) => ANOM_ORDER_NAMES[v]} fn={setAnomOrder} />
        </> : <>
            <Text mt="1" fontWeight="bold">Order:</Text>
            <RadioButtonGroup name="order" value={order} options={orderOptions(obs, period)} optFormat={(value) => ORDER_NAMES[value]} fn={setOrder} />
        </>}
        <Text mt="1" fontWeight="bold">Results:</Text>
        <RadioButtonGroup name="limit" value={limit} options={["10", "25", "50", "100"]} optFormat={(value) => value + " rows"} fn={setLimit} />

        {period === "spells" ? <SpellRankingTable
            obs={obs}
            dailyAggregation={dailyAggregation}
            dir={dir}
            threshold={spellThreshold}
            month={month}
            startYear={startYear}
            limit={limit}
        /> : period === "anom" ? <AnomSpellRankingTable
            dailyAggregation={dailyAggregation}
            dir={dir}
            level={anomLevel}
            order={anomOrder}
            month={month}
            limit={limit}
        /> : period === "rolling" ? <RollingRankingTable
            obs={obs}
            dailyAggregation={dailyAggregation}
            days={days}
            month={month}
            order={order}
            limit={limit}
        /> : <RankingTable
            obs={obs}
            dailyAggregation={dailyAggregation}
            period={period}
            summary={summary}
            threshold={threshold}
            month={month}
            window={window}
            centre={centre}
            order={order}
            limit={limit}
        />}
        <Text mt="3">
            Daily rankings compare the selected daily series directly. A day window (±5 or ±15 days around a centre
            date) keeps only calendar days near that date in every year (for example 10–20 October for a centre of
            15 October); year-end wrap and 29 February are included when they fall in the window. Monthly rankings
            first summarize that same daily series within each month. Rankings use records from {REPORT_YEAR_START} onward.
        </Text>
        <Text mt="2">
            Annual rankings use calendar years; water-year rankings (rainfall and wet hours only) use 1 October to 30 September,
            labelled by the year they end (e.g. {waterYearLabel(2026)} = {waterYearRange(2026)}). Both only rank
            complete years: the current, still in-progress year and any partially recorded first year are left out.
        </Text>
        <Text mt="2">
            Multi-day rankings use N consecutive days: the total (rainfall, wet hours, sunshine), or the mean of the
            chosen daily statistic. Listed periods never overlap, so one storm or heatwave appears only once. A
            period needs data for at least 90% of its days ({MIN_COVERAGE[5]} of 5, {MIN_COVERAGE[7]} of 7, {MIN_COVERAGE[14]} of 14,
            {" "}{MIN_COVERAGE[30]} of 30); means and sunshine totals only use complete days, so today is left out.
            With a month or season selected, any period overlapping that month or season is included.
        </Text>
        <Text mt="2">
            Heat / cold spells are runs of consecutive days on which the daily high, low or mean departs from the
            1991–2020 climate normal by at least the chosen amount (heatwave above, cold snap below). They can be
            ranked by length, cumulative departure, or peak departure. Temperatures stop at yesterday.
        </Text>
        <Text mt="2">
            Spells are runs of consecutive days on which the chosen daily value is at or above (≥), or below (&lt;),
            the threshold, ranked by length; ties list the most recent first. A day without data ends a spell. With a
            month or season selected, any spell overlapping that month or season is included in full. Rain and wet-hour
            spells include today once it qualifies; other variables stop at yesterday.
        </Text>
    </Page>;
}
