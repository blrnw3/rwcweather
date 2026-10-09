import { Box, Flex, Grid, Heading, Spinner, Text } from "@chakra-ui/react";
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
import { useWaterYears, WaterYearCell, WaterYearHeader, WaterYearNote } from "../../components/waterYear";

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const months = Array.from(Array(12).keys());

function useSummaries(obs, dailyAggregation) {
    const url = "/api/var/all_periods/" + obs + "/" + dailyAggregation
        + "/?start=" + REPORT_YEAR_START + "0101&include_today=1";
    return useSWR(url, fetcher, { refreshInterval: 300000 });
}

// Shared by the year-by-month matrix and the all-time summary so both always
// show the same underlying values for the selected variable and statistics.
function useMatrixData(obs, dailyAggregation, summary, threshold) {
    const { data: response, error, isValidating } = useSummaries(obs, dailyAggregation);
    const results = response?.result || {};
    const serverDate = response?.server?.date || [new Date().getFullYear(), new Date().getMonth() + 1, 1];
    const currentYear = serverDate[0];
    const currentMonth = serverDate[1] - 1;
    const selectedSummaryKey = summaryKey(summary);

    const matrix = new Map();
    const annual = new Map();

    if (summary === "count") {
        const numericThreshold = Number(threshold);
        for (const result of results.daily || []) {
            const [year, month] = result.d;
            if (!matrix.has(year)) {
                matrix.set(year, new Map());
            }
            if (!matrix.get(year).has(month - 1)) {
                matrix.get(year).set(month - 1, 0);
            }
            if (!annual.has(year)) {
                annual.set(year, 0);
            }
            if (result.val > numericThreshold) {
                matrix.get(year).set(month - 1, matrix.get(year).get(month - 1) + 1);
                annual.set(year, annual.get(year) + 1);
            }
        }
    } else {
        for (const result of results.monthly || []) {
            const [year, month] = result.m;
            if (!matrix.has(year)) {
                matrix.set(year, new Map());
            }
            matrix.get(year).set(month - 1, result.summary[selectedSummaryKey]);
        }
        for (const result of results.yearly || []) {
            annual.set(result.m, result.summary[selectedSummaryKey]);
        }
    }

    return { matrix, annual, currentYear, currentMonth, response, error, isValidating };
}

function MonthlyMatrix({ obs, dailyAggregation, summary, threshold }) {
    const obsObj = OBS.get(obs);
    const unit = useContext(UnitCtx);
    const { matrix, annual, currentYear, currentMonth, response, error, isValidating }
        = useMatrixData(obs, dailyAggregation, summary, threshold);
    // Rain also gets a water-year column; from October the in-progress water
    // year ends next calendar year, so it needs its own (otherwise future) row.
    const waterYears = useWaterYears(obs, summary, threshold);
    const lastYear = Math.max(currentYear, waterYears?.currentWaterYear || currentYear);
    const years = Array.from(Array(lastYear - REPORT_YEAR_START + 1).keys())
        .map((offset) => lastYear - offset);

    return <Grid id="obs-monthly-matrix"
        templateColumns={"0.8fr repeat(" + (waterYears ? 14 : 13) + ", 1fr)"}
        templateRows="30px auto"
        overflow="auto"
        marginTop="4"
        columnGap={{ base: 1, md: 2, lg: 3, xl: 5 }}
    >
        <Flex justifyContent="center" fontSize="lg">
            {isValidating && !response ? <Spinner size="sm" /> : obsObj.icon}
        </Flex>
        {months.map((month) =>
            <Box key={month} fontWeight="bold" textAlign="center">{monthNames[month]}</Box>
        )}
        <Box fontWeight="bold" textAlign="center">Annual</Box>
        {waterYears && <WaterYearHeader />}
        {years.map((year) =>
            <Box key={year} display="contents">
                <Box minW="46px" py="2" fontWeight="bold" textAlign="center">{year}</Box>
                {months.map((month) => {
                    const isFuture = year > currentYear || (year === currentYear && month > currentMonth);
                    const hasValue = matrix.get(year)?.has(month);
                    const value = hasValue ? matrix.get(year).get(month) : null;
                    const formattedValue = summary === "count"
                        ? (value == null ? "-" : value.toString())
                        : formatObs(unit, value, obsObj.fmat, false, false);
                    const { bg, col } = isFuture
                        ? { bg: "gray.200", col: "black" }
                        : styleForReportValue(value, obsObj.fmat, unit, summary);

                    return <Box key={year + "-" + month}
                        className="cell"
                        textAlign="center"
                        backgroundColor={bg}
                        color={col}
                        border="1px solid transparent"
                        _hover={hasValue ? { border: "1px solid " + col } : {}}
                        py="2"
                        px="1"
                    >
                        {isFuture ? "" : formattedValue}
                    </Box>;
                })}
                {(() => {
                    const hasValue = annual.has(year);
                    const value = hasValue ? annual.get(year) : null;
                    const isFuture = year > currentYear;
                    const formattedValue = isFuture ? "" : summary === "count"
                        ? (value == null ? "-" : value.toString())
                        : formatObs(unit, value, obsObj.fmat, false, false);
                    const { bg, col } = isFuture
                        ? { bg: "gray.200", col: "black" }
                        : styleForReportValue(value, obsObj.fmat, unit, summary, true);

                    return <Box key={year + "-annual"}
                        className="cell annual"
                        textAlign="center"
                        backgroundColor={bg}
                        color={col}
                        border="1px solid transparent"
                        borderLeft="2px solid"
                        borderLeftColor="gray.400"
                        _hover={hasValue ? { border: "1px solid " + col, borderLeft: "2px solid" } : {}}
                        py="2"
                        px="1"
                    >
                        {formattedValue}
                    </Box>;
                })()}
                {waterYears && <WaterYearCell waterYear={year} data={waterYears} obs={obs} unit={unit} summary={summary} />}
            </Box>
        )}
        {error && <Text gridColumn="1 / -1" color="red.600">Unable to load monthly data.</Text>}
        {waterYears?.error && <Text gridColumn="1 / -1" color="red.600">Unable to load water-year data.</Text>}
        {waterYears && <Box gridColumn="1 / -1"><WaterYearNote data={waterYears} obs={obs} unit={unit} summary={summary} /></Box>}
    </Grid>;
}

function calcStats(values) {
    const valid = values.filter((v) => v != null && !Number.isNaN(v));
    if (valid.length === 0) {
        return null;
    }
    return {
        min: Math.min(...valid),
        max: Math.max(...valid),
        avg: valid.reduce((a, b) => a + b, 0) / valid.length,
        n: valid.length,
    };
}

// Per-month and annual min/max/avg across years. Years without a value are
// skipped (not counted as zero). The in-progress month and year are left out
// because their partial totals/means would skew the all-time figures.
function allTimeStats(matrix, annual, currentYear, currentMonth) {
    const byMonth = months.map((month) => {
        const values = [];
        for (const [year, monthMap] of matrix) {
            if (year === currentYear && month >= currentMonth) {
                continue;
            }
            if (monthMap.has(month)) {
                values.push(monthMap.get(month));
            }
        }
        return calcStats(values);
    });

    const annualValues = [];
    for (const [year, value] of annual) {
        if (year !== currentYear) {
            annualValues.push(value);
        }
    }

    return { byMonth, annual: calcStats(annualValues) };
}

function AllTimeSummary({ obs, dailyAggregation, summary, threshold }) {
    const obsObj = OBS.get(obs);
    const unit = useContext(UnitCtx);
    const { matrix, annual, currentYear, currentMonth, response, error, isValidating }
        = useMatrixData(obs, dailyAggregation, summary, threshold);
    const stats = allTimeStats(matrix, annual, currentYear, currentMonth);

    const rows = [
        { key: "min", label: "Min" },
        { key: "max", label: "Max" },
        { key: "avg", label: "Avg" },
    ];

    const formatValue = (value, key) => {
        if (value == null) {
            return "-";
        }
        if (summary === "count") {
            return key === "avg" ? value.toFixed(1) : value.toString();
        }
        return formatObs(unit, value, obsObj.fmat, false, false);
    };

    return <Grid id="obs-alltime-summary"
        templateColumns="0.8fr repeat(13, 1fr)"
        templateRows="30px auto"
        overflow="auto"
        marginTop="4"
        columnGap={{ base: 1, md: 2, lg: 3, xl: 5 }}
    >
        <Flex justifyContent="center" fontSize="lg">
            {isValidating && !response ? <Spinner size="sm" /> : obsObj.icon}
        </Flex>
        {months.map((month) =>
            <Box key={month} fontWeight="bold" textAlign="center">{monthNames[month]}</Box>
        )}
        <Box fontWeight="bold" textAlign="center">Annual</Box>
        {rows.map(({ key, label }) =>
            <Box key={key} display="contents">
                <Box minW="46px" py="2" fontWeight="bold" textAlign="center">{label}</Box>
                {months.map((month) => {
                    const value = stats.byMonth[month]?.[key] ?? null;
                    const { bg, col } = styleForReportValue(value, obsObj.fmat, unit, summary);

                    return <Box key={month + "-" + key}
                        className="cell"
                        textAlign="center"
                        backgroundColor={bg}
                        color={col}
                        border="1px solid transparent"
                        _hover={value != null ? { border: "1px solid " + col } : {}}
                        py="2"
                        px="1"
                    >
                        {formatValue(value, key)}
                    </Box>;
                })}
                {(() => {
                    const value = stats.annual?.[key] ?? null;
                    const { bg, col } = styleForReportValue(value, obsObj.fmat, unit, summary, true);

                    return <Box key={key + "-annual"}
                        className="cell annual"
                        textAlign="center"
                        backgroundColor={bg}
                        color={col}
                        border="1px solid transparent"
                        borderLeft="2px solid"
                        borderLeftColor="gray.400"
                        _hover={value != null ? { border: "1px solid " + col, borderLeft: "2px solid" } : {}}
                        py="2"
                        px="1"
                    >
                        {formatValue(value, key)}
                    </Box>;
                })()}
            </Box>
        )}
        {error && <Text gridColumn="1 / -1" color="red.600">Unable to load summary data.</Text>}
    </Grid>;
}

export default function AllTimeReport() {
    const [obs, setObs] = useState("temp");
    const [dailyAggregation, setDailyAggregation] = useState("avg");
    const [summary, setSummary] = useState("avg");
    const [threshold, setThreshold] = useState("0");
    const dailyOptions = dailyAggregationOptions(obs);
    const monthlySummaryOptions = summaryOptions(obs);

    const handleObsChange = (nextObs) => {
        setObs(nextObs);
        setDailyAggregation(OBS.get(nextObs).summary);
        setThreshold("0");
        const nextMiddleSummary = OBS.get(nextObs).summary;
        if (summary === "avg" || summary === "total") {
            setSummary(nextMiddleSummary);
        }
    };

    return <Page name="reports" sub="all-time" title="Reports | all-time">
        <Heading as="h1" size="1">Reports: All-time</Heading>
        <Heading as="h2" size="2">
            {SUMMARY_NAMES[summary]} of {DAILY_AGGREGATION_NAMES[dailyAggregation]} {OBS.get(obs).name}
        </Heading>

        <Text fontWeight="bold">Variable:</Text>
        <RadioButtonGroup name="obs" value={obs} options={REPORT_OBS_OPTIONS} optFormat={fmatObsOpt} fn={handleObsChange} />
        <Text mt="1" fontWeight="bold">Daily statistic:</Text>
        <RadioButtonGroup
            name="daily-aggregation"
            value={dailyAggregation}
            options={dailyOptions}
            optFormat={(value) => DAILY_AGGREGATION_NAMES[value]}
            fn={setDailyAggregation}
        />
        <Text mt="1" fontWeight="bold">Monthly and annual summary:</Text>
        <RadioButtonGroup name="summary" value={summary} options={monthlySummaryOptions} optFormat={(value) => SUMMARY_NAMES[value]} fn={setSummary} />
        {summary === "count" && <CountThresholdSelector obs={obs} value={threshold} fn={setThreshold} />}

        <MonthlyMatrix obs={obs} dailyAggregation={dailyAggregation} summary={summary} threshold={threshold} />

        <Heading as="h3" size="3" mt="6">Min, max and average across all years</Heading>
        <AllTimeSummary obs={obs} dailyAggregation={dailyAggregation} summary={summary} threshold={threshold} />

        <Text mt="3">
            Choose a daily series first, then summarize those daily values independently for each month and year.
            Count is the number of selected daily values above the chosen threshold. Rainfall uses daily totals.
        </Text>
        <Text mt="2">
            The table above compares the same month (or full year) across years: its min, max and average are
            taken over the values in the matrix. Years with no data for a month are ignored rather than counted as
            zero. The current, still in-progress month and year are excluded so partial data does not skew the results.
        </Text>
    </Page>;
}
