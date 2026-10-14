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
import { useContext } from "react";
import useSWR from "swr";
import { baseObs, defaultDailyStat, fetcher, fmatObsOpt, isTotalObs, OBS } from "../../components/conf";
import { ClimateNormalsLink } from "../../components/climate";
import { Page, UnitCtx } from "../../components/Page";
import { inList, useUrlState } from "../../components/urlState";
import {
    COUNT_THRESHOLDS,
    CountThresholdSelector,
    DAILY_AGGREGATION_NAMES,
    dailyAggregationOptions,
    RadioButtonGroup,
    DAILY_VALUE_OBS_OPTIONS,
    DAILY_VALUE_OBS_STATES,
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
    monthly: "Monthly",
    annual: "Annual",
    wateryear: "Water year",
};

// Periods built by summarising daily values (all but "daily" itself).
const SUMMARY_PERIODS = ["monthly", "annual", "wateryear"];

// Multi-day periods: N consecutive days, ranked server-side from the daily
// table (see rwcwx/calc/rolling.py). Rain and sunshine totals, temperature means.
const ROLLING_OBS = ["rain", "temp", "sun", "sunpct", "wet"];
const ROLLING_DAYS = ["3", "7", "14", "30"];
const MIN_COVERAGE = { 3: 3, 7: 7, 14: 13, 30: 27 };

// Spells: longest runs of consecutive days above (>=) or below (<) a threshold, ranked server-side
// (see rwcwx/calc/spells.py). Thresholds are in inches, °F or hours, mirroring SPELL_VARS there.
const SPELL_CONF = {
    rain: { total: ["0.01", "0.1", "0.25", "0.5", "1"] },
    wet: { total: ["1", "3", "6", "12"] },
    temp: {
        max: ["40", "50", "60", "70", "80", "90", "100"],
        min: ["32", "40", "45", "50", "55", "60"],
        avg: ["40", "50", "60", "70", "80"],
    },
    sun: { total: ["0.1", "1", "4", "8", "10", "12"] },
};
const SPELL_OBS = Object.keys(SPELL_CONF);
// Opening defaults: wet days for rain, warm days for temperatures, sunny days for sunshine.
const SPELL_DEFAULTS = { rain: "0.01", wet: "1", max: "80", min: "50", avg: "60", sun: "10" };
const SPELL_DIR_NAMES = {
    rain: { above: "Wet (≥)", below: "Dry (<)" },
    wet: { above: "Wet (≥)", below: "Mostly dry (<)" },
    temp: { above: "Above (≥)", below: "Below (<)" },
    sun: { above: "Sunny (≥)", below: "Dull (<)" },
};
const SPELL_TITLE_WORDS = {
    rain: { above: "wet", below: "dry" },
    wet: { above: "wet", below: "mostly dry" },
    temp: { above: "warm", below: "cold" },
    sun: { above: "sunny", below: "dull" },
};
const SPELL_STATUS = { today: ", so far", pending: ", may continue today", yesterday: ", to yesterday" };
const SPELL_START_YEARS = ["all", ...Array.from(Array(new Date().getFullYear() - 2021 + 1).keys()).map((i) => String(2021 + i))];

function spellThresholds(obs, stat) {
    return SPELL_CONF[obs]?.[stat] || [];
}

function spellDefaultThreshold(obs, stat) {
    const list = spellThresholds(obs, stat);
    const def = SPELL_DEFAULTS[obs === "temp" ? stat : obs];
    return list.includes(def) ? def : list[0];
}

// Thresholds are entered in °F / inches / hours; temperatures are stored (and formatted from) °C.
function formatThreshold(unit, obs, value) {
    if (obs === "wet" || obs === "sun") {
        return value + " h";
    }
    const stored = obs === "temp" ? (Number(value) - 32) * 5 / 9 : Number(value);
    return formatObs(unit, stored, OBS.get(obs).fmat);
}

function periodOptions(obs) {
    return [
        "daily",
        ...(ROLLING_OBS.includes(obs) ? ["rolling"] : []),
        ...(SPELL_OBS.includes(obs) ? ["spells"] : []),
        "monthly",
        "annual",
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
const monthOptions = ["all", ...Array.from(Array(12).keys()).map((month) => (month + 1).toString())];

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

function CurrentContext({ label, periodLabel, value, rank, of, inTop, soFar = true }) {
    return <Text id="ranking-current" mt="3" p="2" bg="blue.50" borderLeftWidth="4px" borderColor="blue.400">
        <b>{label}{soFar ? " so far" : ""}</b> ({periodLabel}): <b>{value}</b>
        {rank != null ? <>, rank <b>{rank}</b> of {of}{inTop ? " (in the list below)" : ""}</> : null}
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

function RollingRankingTable({ obs, dailyAggregation, days, order, limit }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);
    const url = "/api/var/rolling/" + obs + "/" + dailyAggregation + "/?days=" + days + "&order=" + order + "&limit=" + limit;
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

    return <Box mt="5" overflowX="auto">
        {isValidating && <Text color="gray.500" fontSize="sm">Refreshing…</Text>}
        {current ? <CurrentContext
            label={"Latest " + days + " days"}
            periodLabel={formatSpan(current.start, current.end)}
            value={formatObs(unit, current.val, obsObj.fmat)}
            rank={current.rank}
            of={current.of}
            inTop={currentInTop}
            soFar={today != null && current.end.join("-") === today.join("-")}
        /> : <Text mt="3" color="gray.500">The latest {days} days don't have enough data to rank.</Text>}
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
                    const { bg, col } = styleForReportValue(record.val, obsObj.fmat, unit, isTotalObs(obs) ? "total" : null);
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
                        <Td isNumeric backgroundColor={bg} color={col}>{formatObs(unit, record.val, obsObj.fmat)}</Td>
                    </Tr>;
                })}
                {showCurrentRow && <Tr id="ranking-current-row" borderTopWidth="3px" borderTopStyle="dashed">
                    <Td isNumeric fontWeight="bold" bg="blue.50">{current.rank}</Td>
                    <Td bg="blue.50">Latest {days} days: {formatSpan(current.start, current.end)}
                        {current.days < current.n && <Text as="span" color="gray.500" fontSize="sm">
                            {" "}({current.days} of {current.n} days with data)
                        </Text>}
                    </Td>
                    <Td isNumeric bg="blue.50">{formatObs(unit, current.val, obsObj.fmat)}</Td>
                </Tr>}
            </Tbody>
        </Table>
        {records.length === 0 && <Text py="4">No ranking data is available.</Text>}
    </Box>;
}

// Inside <Page>, so they can read the unit preference.
function SpellTitle({ obs, dailyAggregation, dir, threshold, limit }) {
    const unit = useContext(UnitCtx);
    return <>Longest {limit} {SPELL_TITLE_WORDS[obs][dir]} spells
        ({DAILY_AGGREGATION_NAMES[dailyAggregation]} {dir === "above" ? "≥" : "<"} {formatThreshold(unit, obs, threshold)}) –</>;
}

function SpellThresholdSelector({ obs, dailyAggregation, value, fn }) {
    const unit = useContext(UnitCtx);
    return <>
        <Text mt="1" fontWeight="bold">Threshold:</Text>
        <RadioButtonGroup name="level" value={value} options={spellThresholds(obs, dailyAggregation)}
            optFormat={(v) => formatThreshold(unit, obs, v)} fn={fn} />
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

function SpellRankingTable({ obs, dailyAggregation, dir, threshold, month, startYear, limit }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);
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
    const fmt = (v) => formatObs(unit, v, obsObj.fmat);
    const days = (n) => n + (n === 1 ? " day" : " days");
    let previousLength = null;
    let displayedRank = 0;

    return <Box mt="5" overflowX="auto">
        {isValidating && <Text color="gray.500" fontSize="sm">Refreshing…</Text>}
        {current ? <Text id="ranking-current" mt="3" p="2" bg="blue.50" borderLeftWidth="4px" borderColor="blue.400">
            <b>Current spell</b> ({formatSpan(current.start, current.end)}{SPELL_STATUS[current.status]}):
            {" "}<b>{days(current.length)}</b>, rank <b>{current.rank}</b> of {current.of}{currentInTop ? " (in the list below)" : ""}
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

function RankingTable({ obs, dailyAggregation, period, summary, threshold, month, order, limit }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);
    const { data: response, error, isValidating } = useRankingData(obs, dailyAggregation);
    const waterYears = useWaterYears(period === "wateryear" ? obs : null, summary, threshold);
    const results = response?.result || {};
    const isSummaryPeriod = SUMMARY_PERIODS.includes(period);
    const byMonth = period === "daily" || period === "monthly";
    const allRecords = rankingRecords(results, response?.server, period, summary, threshold, waterYears)
        .filter((record) => Number.isFinite(record.value))
        .filter((record) => !byMonth || month === "all" || record.date[1] === Number(month))
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
    const currentMonthExcluded = byMonth && month !== "all" && today && Number(month) !== today[1];
    const currentRanked = current != null && Number.isFinite(current.value) && !currentMonthExcluded;
    const otherValues = allRecords.filter((r) => r.date.join("-") !== currentKey).map((r) => r.value);
    const currentRank = currentRanked ? rankOf(current.value, otherValues, order) : null;
    const currentOf = otherValues.length + 1;
    const fmtValue = (value) => summary === "count" && isSummaryPeriod
        ? value.toString()
        : formatObs(unit, value, obsObj.fmat);
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

    return <Box mt="5" overflowX="auto">
        {isValidating && <Text color="gray.500" fontSize="sm">Refreshing…</Text>}
        {currentRanked ? <CurrentContext
            label={CURRENT_LABEL[period]}
            periodLabel={currentPeriodLabel}
            value={fmtValue(current.value)}
            rank={currentRank}
            of={currentOf}
            inTop={currentInTop}
        /> : <Text id="ranking-current" mt="3" color="gray.500">
            {currentMonthExcluded
                ? CURRENT_LABEL[period] + " isn't in " + monthNames[Number(month) - 1] + "; choose All months or "
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
                        : formatObs(unit, record.value, obsObj.fmat);
                    const selectedSummary = isSummaryPeriod ? summary : null;
                    const { bg, col } = styleForReportValue(
                        record.value, obsObj.fmat, unit, selectedSummary, period === "annual" || period === "wateryear", isSummaryPeriod
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

const monthParam = (value) => value === "all" ? "all" : monthNames[Number(value) - 1].toLowerCase();
const monthFromParam = (value) => {
    const index = monthNames.findIndex((name) => name.toLowerCase() === String(value).toLowerCase());
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
        def: () => "0", valid: (v, s) => COUNT_THRESHOLDS[s.obs].includes(v),
        use: (s) => SUMMARY_PERIODS.includes(s.period) && s.summary === "count",
    },
    month: {
        def: () => "all", valid: inList(monthOptions), toUrl: monthParam, fromUrl: monthFromParam,
        use: (s) => s.period === "daily" || s.period === "monthly" || s.period === "spells",
    },
    dir: { def: () => "above", valid: inList(["above", "below"]), use: (s) => s.period === "spells" },
    spellThreshold: {
        param: "level", def: (s) => spellDefaultThreshold(s.obs, s.dailyAggregation),
        valid: (v, s) => spellThresholds(s.obs, s.dailyAggregation).includes(v),
        use: (s) => s.period === "spells",
    },
    startYear: { param: "from", def: () => "all", valid: inList(SPELL_START_YEARS), use: (s) => s.period === "spells" },
    days: { def: () => "3", valid: inList(ROLLING_DAYS), use: (s) => s.period === "rolling" },
    order: { def: () => "highest", valid: (v, s) => orderOptions(s.obs, s.period).includes(v) },
    limit: { param: "rows", def: () => "25", valid: inList(["10", "25", "50", "100"]) },
};

export default function RankingReport() {
    const [state, update] = useUrlState(RANKING_URL_STATE);
    const { period, obs, dailyAggregation, summary, threshold, month, days, order, limit, dir, spellThreshold, startYear } = state;
    const dailyOptions = dailyAggregationOptions(obs);
    const monthlySummaryOptions = summaryOptions(obs);

    const handleObsChange = (nextObs) => update({
        obs: nextObs,
        dailyAggregation: defaultDailyStat(nextObs),
        threshold: "0",
        // Rain is mostly ranked by totals (wettest month / year / water year),
        // so switching to rain selects Total; other summaries stay selectable.
        summary: isTotalObs(nextObs) || summary === "avg" || summary === "total" ? OBS.get(nextObs).summary : summary,
        // Water years are rain-only; other variables fall back to calendar years.
        // Multi-day periods are rain/temperature only; others fall back to daily.
        period: period === "wateryear" && !hasWaterYears(nextObs) ? "annual"
            : period === "rolling" && !ROLLING_OBS.includes(nextObs) ? "daily"
            : period === "spells" && !SPELL_OBS.includes(nextObs) ? "daily" : period,
        spellThreshold: spellDefaultThreshold(nextObs, defaultDailyStat(nextObs)),
    });

    const handlePeriodChange = (nextPeriod) => update({
        period: nextPeriod,
        // Water years exist to compare rain totals, so open them on Total.
        ...(nextPeriod === "wateryear" && nextPeriod !== period ? { summary: OBS.get(obs).summary } : {}),
    });
    const setMonth = (value) => update({ month: value });
    const setDailyAggregation = (value) => update({
        dailyAggregation: value,
        ...(period === "spells" ? { spellThreshold: spellDefaultThreshold(obs, value) } : {}),
    });
    const setSummary = (value) => update({ summary: value });
    const setThreshold = (value) => update({ threshold: value });
    const setOrder = (value) => update({ order: value });
    const setDays = (value) => update({ days: value });
    const setDir = (value) => update({ dir: value });
    const setSpellThreshold = (value) => update({ spellThreshold: value });
    const setStartYear = (value) => update({ startYear: value });
    const setLimit = (value) => update({ limit: value });

    const isSummaryPeriod = SUMMARY_PERIODS.includes(period);
    const byMonth = period === "daily" || period === "monthly" || period === "spells";
    const rankingTitle = period === "spells"
        ? <SpellTitle obs={obs} dailyAggregation={dailyAggregation} dir={dir} threshold={spellThreshold} limit={limit} />
        : period === "daily"
        ? ORDER_NAMES[order] + " " + limit + " " + DAILY_AGGREGATION_NAMES[dailyAggregation]
        : period === "rolling"
        ? ORDER_NAMES[order] + " " + limit + " " + days + "-day " + (isTotalObs(obs) ? "totals" : "means")
            + " of " + DAILY_AGGREGATION_NAMES[dailyAggregation]
        : ORDER_NAMES[order] + " " + limit + " " + PERIOD_NAMES[period] + " " + SUMMARY_NAMES[summary]
            + " of " + DAILY_AGGREGATION_NAMES[dailyAggregation];
    const monthSuffix = !byMonth || month === "all" ? "" : " in " + monthNames[Number(month) - 1];

    return <Page name="reports" sub="ranking" title="Reports | rankings">
        <Heading as="h1" size="1">Reports: Rankings</Heading>
        <Heading as="h2" size="2">
            {rankingTitle} {OBS.get(obs).name}{monthSuffix}
        </Heading>
        <ClimateNormalsLink />

        <Text fontWeight="bold">Period:</Text>
        <RadioButtonGroup name="period" value={period} options={periodOptions(obs)} optFormat={(value) => PERIOD_NAMES[value]} fn={handlePeriodChange} />
        {byMonth && <>
            <Text mt="1" fontWeight="bold">Month:</Text>
            <RadioButtonGroup
                name="month"
                value={month}
                options={monthOptions}
                optFormat={(value) => value === "all" ? "All months" : monthNames[Number(value) - 1]}
                fn={setMonth}
            />
        </>}
        {period === "rolling" && <>
            <Text mt="1" fontWeight="bold">Length:</Text>
            <RadioButtonGroup name="days" value={days} options={ROLLING_DAYS} optFormat={(value) => value + " days"} fn={setDays} />
        </>}
        <Text mt="1" fontWeight="bold">Variable:</Text>
        <RadioButtonGroup name="obs" value={baseObs(obs)} options={DAILY_VALUE_OBS_OPTIONS} optFormat={fmatObsOpt} fn={handleObsChange} />
        <SunViewToggle obs={obs} fn={handleObsChange} />
        <Text mt="1" fontWeight="bold">Daily statistic:</Text>
        <RadioButtonGroup name="daily-aggregation" value={dailyAggregation}
            options={period === "spells" ? dailyOptions.filter((o) => spellThresholds(obs, o).length) : dailyOptions} optFormat={(value) => DAILY_AGGREGATION_NAMES[value]} fn={setDailyAggregation} />
        {isSummaryPeriod && <>
            <Text mt="1" fontWeight="bold">{PERIOD_NAMES[period]} summary:</Text>
            <RadioButtonGroup name="summary" value={summary} options={monthlySummaryOptions} optFormat={(value) => SUMMARY_NAMES[value]} fn={setSummary} />
            {summary === "count" && <CountThresholdSelector obs={obs} value={threshold} fn={setThreshold} />}
        </>}
        {period === "spells" ? <>
            <Text mt="1" fontWeight="bold">Spell:</Text>
            <RadioButtonGroup name="dir" value={dir} options={["above", "below"]} optFormat={(value) => SPELL_DIR_NAMES[obs][value]} fn={setDir} />
            <SpellThresholdSelector obs={obs} dailyAggregation={dailyAggregation} value={spellThreshold} fn={setSpellThreshold} />
            <Text mt="1" fontWeight="bold">From:</Text>
            <RadioButtonGroup name="from" value={startYear} options={SPELL_START_YEARS}
                optFormat={(value) => value === "all" ? "All years" : value} fn={setStartYear} />
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
        /> : period === "rolling" ? <RollingRankingTable
            obs={obs}
            dailyAggregation={dailyAggregation}
            days={days}
            order={order}
            limit={limit}
        /> : <RankingTable
            obs={obs}
            dailyAggregation={dailyAggregation}
            period={period}
            summary={summary}
            threshold={threshold}
            month={month}
            order={order}
            limit={limit}
        />}
        <Text mt="3">
            Daily rankings compare the selected daily series directly. Monthly rankings first summarize that same
            daily series within each month. Rankings use records from {REPORT_YEAR_START} onward.
        </Text>
        <Text mt="2">
            Annual rankings use calendar years; water-year rankings (rainfall and wet hours only) use 1 October to 30 September,
            labelled by the year they end (e.g. {waterYearLabel(2026)} = {waterYearRange(2026)}). Both only rank
            complete years: the current, still in-progress year and any partially recorded first year are left out.
        </Text>
        <Text mt="2">
            Multi-day rankings (rainfall and temperature) use N consecutive days: the rain total, or the mean of the
            chosen daily temperature. Listed periods never overlap, so one storm or heatwave appears only once. A
            period needs data for at least 90% of its days ({MIN_COVERAGE[7]} of 7, {MIN_COVERAGE[14]} of 14,
            {" "}{MIN_COVERAGE[30]} of 30); temperature periods only use complete days, so today is left out.
        </Text>
        <Text mt="2">
            Spells are runs of consecutive days on which the chosen daily value is at or above (≥), or below (&lt;),
            the threshold, ranked by length; ties list the most recent first. A day without data ends a spell. With a
            month selected, only days in that month count, so spells are cut at the month&apos;s edges. Rain and wet-hour
            spells include today once it qualifies; temperature and sunshine spells stop at yesterday.
        </Text>
    </Page>;
}
