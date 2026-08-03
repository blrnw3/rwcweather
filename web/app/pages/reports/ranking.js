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
import { useContext, useState } from "react";
import useSWR from "swr";
import { fetcher, fmatObsOpt, OBS } from "../../components/conf";
import { Page, UnitCtx } from "../../components/Page";
import {
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

const PERIOD_NAMES = {
    daily: "Daily",
    monthly: "Monthly",
};

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

function rankingRecords(results, period, summary, threshold) {
    if (period === "daily") {
        return (results.daily || []).map((result) => ({ date: result.d, value: result.val }));
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
    const results = response?.result || {};
    const records = rankingRecords(results, period, summary, threshold)
        .filter((record) => Number.isFinite(record.value))
        .filter((record) => month === "all" || record.date[1] === Number(month))
        .sort((a, b) => {
            const valueOrder = order === "highest" ? b.value - a.value : a.value - b.value;
            if (valueOrder !== 0) {
                return valueOrder;
            }
            return b.date.join("-").localeCompare(a.date.join("-"));
        })
        .slice(0, Number(limit));

    if (error) {
        return <Text mt="4" color="red.600">Unable to load ranking data.</Text>;
    }
    if (!response) {
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
                    <Th>{period === "daily" ? "Date" : "Month"}</Th>
                    <Th isNumeric>{summary === "count" && period === "monthly" ? "Days" : obsObj.name}</Th>
                </Tr>
            </Thead>
            <Tbody>
                {records.map((record, index) => {
                    if (record.value !== previousValue) {
                        displayedRank = index + 1;
                        previousValue = record.value;
                    }
                    const formattedValue = summary === "count" && period === "monthly"
                        ? record.value.toString()
                        : formatObs(unit, record.value, obsObj.fmat);
                    const selectedSummary = period === "monthly" ? summary : null;
                    const { bg, col } = styleForReportValue(
                        record.value, obsObj.fmat, unit, selectedSummary
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

export default function RankingReport() {
    const [period, setPeriod] = useState("daily");
    const [obs, setObs] = useState("temp");
    const [dailyAggregation, setDailyAggregation] = useState("max");
    const [summary, setSummary] = useState("max");
    const [threshold, setThreshold] = useState("0");
    const [month, setMonth] = useState("all");
    const [order, setOrder] = useState("highest");
    const [limit, setLimit] = useState("25");
    const dailyOptions = dailyAggregationOptions(obs);
    const monthlySummaryOptions = summaryOptions(obs);

    const handleObsChange = (nextObs) => {
        setObs(nextObs);
        setDailyAggregation(nextObs === "rain" ? "total" : "max");
        setThreshold("0");
        if (summary === "avg" || summary === "total") {
            setSummary(OBS.get(nextObs).summary);
        }
    };

    const rankingTitle = period === "daily"
        ? ORDER_NAMES[order] + " " + limit + " " + DAILY_AGGREGATION_NAMES[dailyAggregation]
        : ORDER_NAMES[order] + " " + limit + " Monthly " + SUMMARY_NAMES[summary]
            + " of " + DAILY_AGGREGATION_NAMES[dailyAggregation];
    const monthSuffix = month === "all" ? "" : " in " + monthNames[Number(month) - 1];

    return <Page name="reports" sub="ranking" title="Reports | rankings">
        <Heading as="h1" size="1">Reports: Rankings</Heading>
        <Heading as="h2" size="2">
            {rankingTitle} {OBS.get(obs).name}{monthSuffix}
        </Heading>

        <Text fontWeight="bold">Period:</Text>
        <RadioButtonGroup name="period" value={period} options={["daily", "monthly"]} optFormat={(value) => PERIOD_NAMES[value]} fn={setPeriod} />
        <Text mt="1" fontWeight="bold">Month:</Text>
        <RadioButtonGroup
            name="month"
            value={month}
            options={monthOptions}
            optFormat={(value) => value === "all" ? "All months" : monthNames[Number(value) - 1]}
            fn={setMonth}
        />
        <Text mt="1" fontWeight="bold">Variable:</Text>
        <RadioButtonGroup name="obs" value={obs} options={REPORT_OBS_OPTIONS} optFormat={fmatObsOpt} fn={handleObsChange} />
        <Text mt="1" fontWeight="bold">Daily statistic:</Text>
        <RadioButtonGroup name="daily-aggregation" value={dailyAggregation} options={dailyOptions} optFormat={(value) => DAILY_AGGREGATION_NAMES[value]} fn={setDailyAggregation} />
        {period === "monthly" && <>
            <Text mt="1" fontWeight="bold">Monthly summary:</Text>
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
    </Page>;
}
