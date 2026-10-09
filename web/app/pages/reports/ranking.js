import {
    Box,
    Heading,
    Spinner,
    Table,
    Tbody,
    Td,
    Text,
    Th,
    Thead,
    Tr,
} from "@chakra-ui/react";
import { useContext } from "react";
import useSWR from "swr";
import { fetcher, fmatObsOpt, OBS } from "../../components/conf";
import { ClimateNormalsLink } from "../../components/climate";
import { Page, UnitCtx } from "../../components/Page";
import { inList, useUrlState } from "../../components/urlState";
import {
    COUNT_THRESHOLDS,
    CountThresholdSelector,
    DAILY_AGGREGATION_NAMES,
    dailyAggregationOptions,
    RadioButtonGroup,
    REPORT_OBS_OPTIONS,
    REPORT_YEAR_START,
    SUMMARY_NAMES,
    summaryKey,
    summaryOptions,
    styleForReportValue,
} from "../../components/report";
import { formatObs } from "../../format";
import { hasWaterYears, useWaterYears, waterYearLabel, waterYearRange } from "../../components/waterYear";

const PERIOD_NAMES = {
    daily: "Daily",
    monthly: "Monthly",
    annual: "Annual",
    wateryear: "Water year",
};

// Periods built by summarising daily values (all but "daily" itself).
const SUMMARY_PERIODS = ["monthly", "annual", "wateryear"];

function periodOptions(obs) {
    return hasWaterYears(obs) ? ["daily", "monthly", "annual", "wateryear"] : ["daily", "monthly", "annual"];
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

function RankingTable({ obs, dailyAggregation, period, summary, threshold, month, order, limit }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);
    const { data: response, error, isValidating } = useRankingData(obs, dailyAggregation);
    const waterYears = useWaterYears(period === "wateryear" ? obs : null, summary, threshold);
    const results = response?.result || {};
    const isSummaryPeriod = SUMMARY_PERIODS.includes(period);
    const byMonth = period === "daily" || period === "monthly";
    const records = rankingRecords(results, response?.server, period, summary, threshold, waterYears)
        .filter((record) => Number.isFinite(record.value))
        .filter((record) => !byMonth || month === "all" || record.date[1] === Number(month))
        .sort((a, b) => {
            const valueOrder = order === "highest" ? b.value - a.value : a.value - b.value;
            if (valueOrder !== 0) {
                return valueOrder;
            }
            return b.date.join("-").localeCompare(a.date.join("-"));
        })
        .slice(0, Number(limit));

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
                        record.value, obsObj.fmat, unit, selectedSummary, period === "annual" || period === "wateryear"
                    );

                    return <Tr key={record.date.join("-")}>
                        <Td isNumeric fontWeight="bold">{displayedRank}</Td>
                        <Td>{formatPeriod(period, record.date)}</Td>
                        <Td isNumeric backgroundColor={bg} color={col}>{formattedValue}</Td>
                    </Tr>;
                })}
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

// Selections kept in the URL, e.g. /reports/ranking?var=rain&period=wateryear
// or /reports/ranking?period=monthly&month=jul&order=lowest. Keys resolve in
// order, so the period can depend on the variable (water years: rain only).
const RANKING_URL_STATE = {
    obs: { param: "var", def: () => "temp", valid: inList(REPORT_OBS_OPTIONS) },
    period: { def: () => "daily", valid: (v, s) => periodOptions(s.obs).includes(v) },
    dailyAggregation: {
        param: "daily", def: (s) => s.obs === "rain" ? "total" : "max",
        valid: (v, s) => dailyAggregationOptions(s.obs).includes(v),
    },
    summary: {
        def: (s) => s.obs === "rain" ? "total" : "max",
        valid: (v, s) => summaryOptions(s.obs).includes(v),
        use: (s) => SUMMARY_PERIODS.includes(s.period),
    },
    threshold: {
        def: () => "0", valid: (v, s) => COUNT_THRESHOLDS[s.obs].includes(v),
        use: (s) => SUMMARY_PERIODS.includes(s.period) && s.summary === "count",
    },
    month: {
        def: () => "all", valid: inList(monthOptions), toUrl: monthParam, fromUrl: monthFromParam,
        use: (s) => s.period === "daily" || s.period === "monthly",
    },
    order: { def: () => "highest", valid: inList(["highest", "lowest"]) },
    limit: { param: "rows", def: () => "25", valid: inList(["10", "25", "50", "100"]) },
};

export default function RankingReport() {
    const [state, update] = useUrlState(RANKING_URL_STATE);
    const { period, obs, dailyAggregation, summary, threshold, month, order, limit } = state;
    const dailyOptions = dailyAggregationOptions(obs);
    const monthlySummaryOptions = summaryOptions(obs);

    const handleObsChange = (nextObs) => update({
        obs: nextObs,
        dailyAggregation: nextObs === "rain" ? "total" : "max",
        threshold: "0",
        // Rain is mostly ranked by totals (wettest month / year / water year),
        // so switching to rain selects Total; other summaries stay selectable.
        summary: nextObs === "rain" || summary === "avg" || summary === "total" ? OBS.get(nextObs).summary : summary,
        // Water years are rain-only; other variables fall back to calendar years.
        period: period === "wateryear" && !hasWaterYears(nextObs) ? "annual" : period,
    });

    const handlePeriodChange = (nextPeriod) => update({
        period: nextPeriod,
        // Water years exist to compare rain totals, so open them on Total.
        ...(nextPeriod === "wateryear" && nextPeriod !== period ? { summary: OBS.get(obs).summary } : {}),
    });
    const setMonth = (value) => update({ month: value });
    const setDailyAggregation = (value) => update({ dailyAggregation: value });
    const setSummary = (value) => update({ summary: value });
    const setThreshold = (value) => update({ threshold: value });
    const setOrder = (value) => update({ order: value });
    const setLimit = (value) => update({ limit: value });

    const isSummaryPeriod = SUMMARY_PERIODS.includes(period);
    const byMonth = period === "daily" || period === "monthly";
    const rankingTitle = period === "daily"
        ? ORDER_NAMES[order] + " " + limit + " " + DAILY_AGGREGATION_NAMES[dailyAggregation]
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
        <Text mt="1" fontWeight="bold">Variable:</Text>
        <RadioButtonGroup name="obs" value={obs} options={REPORT_OBS_OPTIONS} optFormat={fmatObsOpt} fn={handleObsChange} />
        <Text mt="1" fontWeight="bold">Daily statistic:</Text>
        <RadioButtonGroup name="daily-aggregation" value={dailyAggregation} options={dailyOptions} optFormat={(value) => DAILY_AGGREGATION_NAMES[value]} fn={setDailyAggregation} />
        {isSummaryPeriod && <>
            <Text mt="1" fontWeight="bold">{PERIOD_NAMES[period]} summary:</Text>
            <RadioButtonGroup name="summary" value={summary} options={monthlySummaryOptions} optFormat={(value) => SUMMARY_NAMES[value]} fn={setSummary} />
            {summary === "count" && <CountThresholdSelector obs={obs} value={threshold} fn={setThreshold} />}
        </>}
        <Text mt="1" fontWeight="bold">Order:</Text>
        <RadioButtonGroup name="order" value={order} options={["highest", "lowest"]} optFormat={(value) => ORDER_NAMES[value]} fn={setOrder} />
        <Text mt="1" fontWeight="bold">Results:</Text>
        <RadioButtonGroup name="limit" value={limit} options={["10", "25", "50", "100"]} optFormat={(value) => value + " rows"} fn={setLimit} />

        <RankingTable
            obs={obs}
            dailyAggregation={dailyAggregation}
            period={period}
            summary={summary}
            threshold={threshold}
            month={month}
            order={order}
            limit={limit}
        />
        <Text mt="3">
            Daily rankings compare the selected daily series directly. Monthly rankings first summarize that same
            daily series within each month. Rankings use records from {REPORT_YEAR_START} onward.
        </Text>
        <Text mt="2">
            Annual rankings use calendar years; water-year rankings (rainfall only) use 1 October to 30 September,
            labelled by the year they end (e.g. {waterYearLabel(2026)} = {waterYearRange(2026)}). Both only rank
            complete years: the current, still in-progress year and any partially recorded first year are left out.
        </Text>
    </Page>;
}
