import { Box, Grid, Text } from "@chakra-ui/react";
import useSWR from "swr";
import { formatObs } from "../format";
import { fetcher, OBS } from "./conf";
import { REPORT_YEAR_START, styleForReportValue } from "./report";

// Water years (Oct 1 - Sep 30) are labelled by the calendar year they end in,
// following the California / USGS convention: WY2026 = 1 Oct 2025 - 30 Sep 2026.
// They only make sense for precipitation, so they are offered for rain alone.
export const WATER_YEAR_START_MONTH = 10;

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Fetch from the start of the water year containing REPORT_YEAR_START so that
// its first water year includes every available record (e.g. late Dec 2020).
const WATER_YEAR_DATA_START = (REPORT_YEAR_START - 1) + "1001";

export function hasWaterYears(obs) {
    return obs === "rain";
}

export function waterYearOf(year, month) {
    return month >= WATER_YEAR_START_MONTH ? year + 1 : year;
}

export function waterYearLabel(waterYear) {
    return "WY" + waterYear;
}

export function waterYearRange(waterYear) {
    return "1 Oct " + (waterYear - 1) + " – 30 Sep " + waterYear;
}

function dateNum(year, month, day) {
    return year * 10000 + month * 100 + day;
}

function formatDateParts([year, month, day]) {
    return day + " " + MONTH_NAMES[month - 1] + " " + year;
}

function summariseValues(values, summary, threshold) {
    if (summary === "count") {
        return values.filter((v) => v > threshold).length;
    }
    if (values.length === 0) {
        return null;
    }
    if (summary === "min") {
        return Math.min(...values);
    }
    if (summary === "max") {
        return Math.max(...values);
    }
    const total = values.reduce((a, b) => a + b, 0);
    return summary === "avg" ? total / values.length : total;
}

// Summarise the daily records of an all_periods response into water years,
// applying the same statistic (total / min / max / count) as the calendar
// columns. Each water year also gets a status:
//  - "complete": the whole Oct-Sep span is covered by the record and has ended
//  - "partial":  records start after 1 Oct, so the year is missing its start
//  - "current":  the water year is still in progress (to date)
export function waterYearSummaries(response, summary, threshold) {
    const daily = response?.result?.daily || [];
    const serverDate = response?.server?.date;
    const today = serverDate ? dateNum(...serverDate) : null;
    const numericThreshold = Number(threshold);

    const byYear = new Map();
    let firstDate = null;
    for (const { d, val } of daily) {
        if (val == null || Number.isNaN(val)) {
            continue;
        }
        const waterYear = waterYearOf(d[0], d[1]);
        if (!byYear.has(waterYear)) {
            byYear.set(waterYear, []);
        }
        byYear.get(waterYear).push(val);
        if (firstDate == null || dateNum(...d) < dateNum(...firstDate)) {
            firstDate = d;
        }
    }

    const waterYears = new Map();
    for (const [waterYear, values] of byYear) {
        let status = "complete";
        let note = waterYearLabel(waterYear) + ": " + waterYearRange(waterYear);
        if (today != null && today <= dateNum(waterYear, 9, 30)) {
            status = "current";
            note = waterYearLabel(waterYear) + " to date: 1 Oct " + (waterYear - 1)
                + " – " + formatDateParts(serverDate);
        } else if (dateNum(...firstDate) > dateNum(waterYear - 1, WATER_YEAR_START_MONTH, 1)) {
            status = "partial";
            note = waterYearLabel(waterYear) + " partial: records start " + formatDateParts(firstDate);
        }
        waterYears.set(waterYear, {
            value: summariseValues(values, summary, numericThreshold),
            days: values.length,
            status,
            note,
        });
    }

    const currentWaterYear = serverDate ? waterYearOf(serverDate[0], serverDate[1]) : null;
    return { waterYears, currentWaterYear, firstDate };
}

// Min / max / average across complete water years only: the in-progress
// water year and any partial first year would skew the all-time figures.
export function completeWaterYearStats(waterYears) {
    const complete = Array.from(waterYears)
        .filter(([, info]) => info.status === "complete" && info.value != null)
        .sort(([a], [b]) => a - b);
    if (complete.length === 0) {
        return null;
    }
    const minEntry = complete.reduce((best, entry) => entry[1].value < best[1].value ? entry : best);
    const maxEntry = complete.reduce((best, entry) => entry[1].value > best[1].value ? entry : best);
    return {
        min: { waterYear: minEntry[0], value: minEntry[1].value },
        max: { waterYear: maxEntry[0], value: maxEntry[1].value },
        avg: complete.reduce((sum, [, info]) => sum + info.value, 0) / complete.length,
        first: complete[0][0],
        last: complete[complete.length - 1][0],
        n: complete.length,
    };
}

// Water-year summaries of daily rain totals (shared SWR key, so every report
// page reuses one request). Returns null for variables without water years.
export function useWaterYears(obs, summary, threshold) {
    const url = hasWaterYears(obs)
        ? "/api/var/all_periods/" + obs + "/total/?start=" + WATER_YEAR_DATA_START + "&include_today=1"
        : null;
    const { data: response, error } = useSWR(url, fetcher, { refreshInterval: 300000 });
    if (!url) {
        return null;
    }
    return { ...waterYearSummaries(response, summary, threshold), response, error };
}

export function formatWaterYearValue(value, obs, unit, summary) {
    if (value == null) {
        return "-";
    }
    if (summary === "count") {
        return Number.isInteger(value) ? value.toString() : value.toFixed(1);
    }
    return formatObs(unit, value, OBS.get(obs).fmat, false, false);
}

export function WaterYearHeader() {
    return <Box fontWeight="bold" textAlign="center" whiteSpace="nowrap"
        title="Water year: 1 Oct – 30 Sep, labelled by the year it ends">
        Water yr
    </Box>;
}

// One cell of the "Water yr" column: the water year ending in `waterYear`.
// Partial and in-progress water years are marked with an asterisk.
export function WaterYearCell({ waterYear, data, obs, unit, summary }) {
    const info = data?.waterYears.get(waterYear);
    const value = info ? info.value : null;
    const flagged = info && info.status !== "complete";
    const { bg, col } = styleForReportValue(value, OBS.get(obs).fmat, unit, summary, true);

    return <Box className={"cell water-year" + (flagged ? " partial" : "")}
        textAlign="center"
        backgroundColor={bg}
        color={col}
        border="1px solid transparent"
        borderLeft="2px solid"
        borderLeftColor="gray.400"
        _hover={info ? { border: "1px solid " + col, borderLeft: "2px solid" } : {}}
        title={info ? info.note : waterYearLabel(waterYear) + ": " + waterYearRange(waterYear)}
        fontStyle={flagged ? "italic" : "normal"}
        py="2"
        px="1"
    >
        {formatWaterYearValue(value, obs, unit, summary)}{flagged ? "*" : ""}
    </Box>;
}

// Explanatory footnote, including min/max/avg over complete water years.
export function WaterYearNote({ data, obs, unit, summary }) {
    if (!data) {
        return null;
    }
    const stats = completeWaterYearStats(data.waterYears);
    const fmt = (value) => formatWaterYearValue(value, obs, unit, summary);
    const flagged = Array.from(data.waterYears)
        .filter(([, info]) => info.status !== "complete")
        .sort(([a], [b]) => b - a)
        .map(([, info]) => info.note);

    return <Box mt="2" id="water-year-note">
        <Text>
            Water yr is the rain year from 1 October to 30 September, labelled by the year it ends
            (e.g. {waterYearLabel(2026)} = {waterYearRange(2026)}), shown alongside the calendar-year Annual figure.
            {flagged.length > 0 && <> * Partial: {flagged.join("; ")}.</>}
        </Text>
        {stats && <Text mt="1">
            Complete water years ({waterYearLabel(stats.first)}–{waterYearLabel(stats.last)}):
            min <b>{fmt(stats.min.value)}</b> ({waterYearLabel(stats.min.waterYear)}),
            max <b>{fmt(stats.max.value)}</b> ({waterYearLabel(stats.max.waterYear)}),
            average <b>{fmt(stats.avg)}</b>. Partial and in-progress water years are excluded.
        </Text>}
    </Box>;
}

// Annual page: calendar-year total alongside the two water years that overlap
// the selected calendar year (the one ending in it and the one starting in it).
export function WaterYearTotals({ year, calendarTotal, serverDate, unit }) {
    const data = useWaterYears("rain", "total", 0);
    const obsObj = OBS.get("rain");
    const yearNum = Number(year);
    const calendarInProgress = serverDate != null && serverDate[0] === yearNum;
    const firstDate = data?.firstDate;
    const calendarPartial = firstDate != null && firstDate[0] === yearNum
        && dateNum(...firstDate) > dateNum(yearNum, 1, 1);
    let calendarRange = "1 Jan – 31 Dec " + yearNum;
    if (calendarInProgress) {
        calendarRange = "to date: 1 Jan – " + formatDateParts(serverDate);
    } else if (calendarPartial) {
        calendarRange = "partial: records start " + formatDateParts(firstDate);
    }
    const columns = [
        {
            key: "calendar",
            label: "Calendar year " + yearNum,
            range: calendarRange,
            value: calendarTotal,
            flagged: calendarInProgress || calendarPartial,
        },
    ];
    for (const waterYear of [yearNum, yearNum + 1]) {
        const info = data?.waterYears.get(waterYear);
        if (!info) {
            continue;
        }
        columns.push({
            key: "wy" + waterYear,
            label: "Water year " + waterYear,
            range: info.status === "complete" ? waterYearRange(waterYear) : info.note.replace(/^WY\d+ /, ""),
            value: info.value,
            flagged: info.status !== "complete",
        });
    }

    return <Box id="water-year-totals" mt="5">
        <Text fontWeight="bold">Rainfall totals</Text>
        <Grid templateColumns={"repeat(" + columns.length + ", minmax(0, 220px))"} columnGap="3" rowGap="1" mt="1">
            {columns.map((c) => <Box key={c.key + "-label"} textAlign="center" fontWeight="bold">{c.label}</Box>)}
            {columns.map((c) => {
                const { bg, col } = styleForReportValue(c.value, obsObj.fmat, unit, "total", true);
                return <Box key={c.key + "-value"}
                    className={"cell " + c.key}
                    textAlign="center"
                    backgroundColor={bg}
                    color={col}
                    fontStyle={c.flagged ? "italic" : "normal"}
                    py="2"
                    px="1"
                >
                    {formatWaterYearValue(c.value, "rain", unit, "total")}{c.flagged ? "*" : ""}
                </Box>;
            })}
            {columns.map((c) => <Box key={c.key + "-range"} textAlign="center" fontSize="sm" color="gray.500">
                {c.flagged ? "* " : ""}{c.range}
            </Box>)}
        </Grid>
    </Box>;
}
