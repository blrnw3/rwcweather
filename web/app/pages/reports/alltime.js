import { Box, Flex, Grid, Heading, Spinner, Text } from "@chakra-ui/react";
import { useContext } from "react";
import useSWR from "swr";
import { fetcher, fmatObsOpt, OBS } from "../../components/conf";
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
import { annualNormal, ClimateAnom, ClimateNormalsLink, ClimateNote, hasClimate, monthlyNormal } from "../../components/climate";
import {
    completeWaterYearStats, useWaterYears, WaterYearCell, WaterYearHeader, WaterYearNote,
} from "../../components/waterYear";

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
    // Climate comparison (as on nw3weather) only for the mean / total summary
    // of a daily series that has normals, e.g. mean of daily highs, rain total.
    const showClimate = summary === obsObj.summary && hasClimate(obs, dailyAggregation);

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
                        {showClimate && !isFuture && <ClimateAnom value={value} obs={obs} stat={dailyAggregation} unit={unit}
                            normal={monthlyNormal(obs, dailyAggregation, month + 1)} />}
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
                        {showClimate && !isFuture && <ClimateAnom value={value} obs={obs} stat={dailyAggregation} unit={unit}
                            normal={annualNormal(obs, dailyAggregation)} />}
                    </Box>;
                })()}
                {waterYears && <WaterYearCell waterYear={year} data={waterYears} obs={obs} unit={unit} summary={summary}
                    showClimate={showClimate} />}
            </Box>
        )}
        {error && <Text gridColumn="1 / -1" color="red.600">Unable to load monthly data.</Text>}
        {waterYears?.error && <Text gridColumn="1 / -1" color="red.600">Unable to load water-year data.</Text>}
        {waterYears && <Box gridColumn="1 / -1"><WaterYearNote data={waterYears} obs={obs} unit={unit} summary={summary}
            showClimate={showClimate} /></Box>}
        {showClimate && <ClimateNote gridColumn="1 / -1" />}
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
    // Same water-year column as the matrix (rain only), over complete water
    // years: the in-progress and any partial first water year are left out.
    const waterYears = useWaterYears(obs, summary, threshold);
    const waterYearStats = waterYears ? completeWaterYearStats(waterYears.waterYears) : null;

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
                {waterYears && (() => {
                    const entry = waterYearStats?.[key];
                    const value = entry == null ? null : key === "avg" ? entry : entry.value;
                    const { bg, col } = styleForReportValue(value, obsObj.fmat, unit, summary, true);

                    return <Box key={key + "-water-year"}
                        className="cell annual water-year-summary"
                        textAlign="center"
                        backgroundColor={bg}
                        color={col}
                        border="1px solid transparent"
                        borderLeft="2px solid"
                        borderLeftColor="gray.400"
                        _hover={value != null ? { border: "1px solid " + col, borderLeft: "2px solid" } : {}}
                        title={entry?.waterYear ? "WY" + entry.waterYear
                            : waterYearStats ? "Complete water years WY" + waterYearStats.first + "–WY" + waterYearStats.last
                                : undefined}
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

// Selections kept in the URL, e.g. /reports/alltime?var=rain&summary=count&threshold=0.1
const ALLTIME_URL_STATE = {
    obs: { param: "var", def: () => "temp", valid: inList(REPORT_OBS_OPTIONS) },
    dailyAggregation: {
        param: "daily", def: (s) => OBS.get(s.obs).summary, valid: (v, s) => dailyAggregationOptions(s.obs).includes(v),
    },
    summary: { def: (s) => OBS.get(s.obs).summary, valid: (v, s) => summaryOptions(s.obs).includes(v) },
    threshold: {
        def: () => "0", valid: (v, s) => COUNT_THRESHOLDS[s.obs].includes(v), use: (s) => s.summary === "count",
    },
};

export default function AllTimeReport() {
    const [{ obs, dailyAggregation, summary, threshold }, update] = useUrlState(ALLTIME_URL_STATE);
    const dailyOptions = dailyAggregationOptions(obs);
    const monthlySummaryOptions = summaryOptions(obs);

    // Switching variable resets the daily statistic and threshold; a Mean/Total
    // summary follows the new variable (Min/Max/Count are kept).
    const handleObsChange = (nextObs) => update({
        obs: nextObs,
        dailyAggregation: OBS.get(nextObs).summary,
        threshold: "0",
        summary: summary === "avg" || summary === "total" ? OBS.get(nextObs).summary : summary,
    });
    const setDailyAggregation = (value) => update({ dailyAggregation: value });
    const setSummary = (value) => update({ summary: value });
    const setThreshold = (value) => update({ threshold: value });

    return <Page name="reports" sub="all-time" title="Reports | all-time">
        <Heading as="h1" size="1">Reports: All-time</Heading>
        <Heading as="h2" size="2">
            {SUMMARY_NAMES[summary]} of {DAILY_AGGREGATION_NAMES[dailyAggregation]} {OBS.get(obs).name}
        </Heading>
        <ClimateNormalsLink />

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
            zero. The current, still in-progress month and year are excluded so partial data does not skew the results;
            for rain, the Water yr column likewise covers complete water years only (in-progress and partial
            water years are excluded).
        </Text>
    </Page>;
}
