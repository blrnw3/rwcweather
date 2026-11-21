import { Box, Flex, Grid, Heading, Spinner, Text } from "@chakra-ui/react";
import { useContext } from "react";
import useSWR from "swr";
import { baseObs, defaultDailyStat, fetcher, fmatForObs, fmatObsOpt, isTotalObs, OBS } from "../../components/conf";
import { Page, UnitCtx } from "../../components/Page";
import { inList, useUrlState } from "../../components/urlState";
import {
    countThresholdsAny,
    CountThresholdSelector,
    DAILY_AGGREGATION_NAMES,
    dailyAggName,
    dailyAggregationOptions,
    RadioButtonGroup,
    DAILY_VALUE_OBS_OPTIONS,
    MULTIDAY_OBS_STATES,
    SUMMARY_NAMES,
    summaryKey,
    summaryOptions,
    styleForReportValue,
    dataYearStart,
    DerivedVarNote,
    EstMark,
    EstNote,
    EstToggle,
    estQuery,
    isEstOn,
    StatButtons,
    SunViewToggle,
} from "../../components/report";
import {
    SPELL_OBS,
    SpellKindSelector,
    SpellThresholdSelector,
    formatSpellLength,
    hasSpellOptions,
    spellDailyStats,
    spellDefaultThreshold,
    spellSummaryLabel,
    spellThresholdsAny,
} from "../../components/spells";
import { formatObs } from "../../format";
import { annualNormal, ClimateAnom, ClimateNormalsLink, ClimateNote, hasClimate, monthlyNormal, seasonalNormal, waterYearNormal } from "../../components/climate";
import {
    completeWaterYearStats, useWaterYears, WaterYearCell, WaterYearHeader, WaterYearNote,
} from "../../components/waterYear";
import {
    isSeasonCurrentOrFuture, isSeasonFuture, PERIOD_LABELS, PERIODS, SEASON_LABELS, SEASONS, seasonOf,
} from "../../components/seasons";

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const months = Array.from(Array(12).keys());

function useSummaries(obs, dailyAggregation, est, enabled = true) {
    const url = enabled
        ? "/api/var/all_periods/" + obs + "/" + dailyAggregation
            + "/?start=" + dataYearStart(est) + "0101&include_today=1" + estQuery(est)
        : null;
    return useSWR(url, fetcher, { refreshInterval: 300000 });
}

function useSpellGrid(obs, dailyAggregation, dir, threshold, est, enabled = true) {
    const url = enabled
        ? "/api/var/spells_grid/" + obs + "/" + dailyAggregation
            + "/?dir=" + dir + "&threshold=" + threshold
            + "&start=" + dataYearStart(est) + "0101" + estQuery(est)
        : null;
    return useSWR(url, fetcher, { refreshInterval: 300000 });
}

function allTimeSummaryOptions(obs) {
    return summaryOptions(obs, { spells: SPELL_OBS.includes(obs) });
}

function isDayLength(summary) {
    return summary === "count" || summary === "spells";
}

function spellOpts(summary, dir, spellThreshold, dailyAggregation) {
    return summary === "spells"
        ? { dir, threshold: spellThreshold, dailyAggregation }
        : null;
}

function defaultDailyFor(obs, summary) {
    let typ = obs === "wind" || obs === "gust" ? "max" : defaultDailyStat(obs, OBS.get(obs).summary);
    if (summary === "spells" && !hasSpellOptions(obs, typ)) {
        typ = spellDailyStats(obs)[0] || typ;
    }
    return typ;
}

// Shared by the year-by-month matrix and the all-time summary so both always
// show the same underlying values for the selected variable and statistics.
function useMatrixData(obs, dailyAggregation, summary, threshold, est, dir, spellThreshold, period = "monthly") {
    const summaries = useSummaries(obs, dailyAggregation, est, summary !== "spells");
    const spells = useSpellGrid(obs, dailyAggregation, dir, spellThreshold, est, summary === "spells");
    const { data: response, error, isValidating } = summary === "spells" ? spells : summaries;
    const results = response?.result || {};
    const serverDate = response?.server?.date || [new Date().getFullYear(), new Date().getMonth() + 1, 1];
    const currentYear = serverDate[0];
    const currentMonth = serverDate[1] - 1;
    const selectedSummaryKey = summaryKey(summary);
    const seasonal = period === "seasonal";

    const matrix = new Map();
    const annual = new Map();
    const estMonths = new Map(); // year -> Set of column keys (month index or season name)
    const estYears = new Set();
    const sharedMonths = new Map();
    const sharedYears = new Set();

    const ensureYear = (year) => {
        if (!matrix.has(year)) {
            matrix.set(year, new Map());
        }
    };
    const markCell = (year, key) => {
        if (!estMonths.has(year)) {
            estMonths.set(year, new Set());
        }
        estMonths.get(year).add(key);
    };
    const markShared = (year, key) => {
        if (!sharedMonths.has(year)) {
            sharedMonths.set(year, new Set());
        }
        sharedMonths.get(year).add(key);
    };

    if (summary === "spells") {
        const rows = seasonal ? (results.seasonal || []) : (results.monthly || []);
        for (const result of rows) {
            const [year, col] = seasonal ? result.m : [result.m[0], result.m[1] - 1];
            ensureYear(year);
            matrix.get(year).set(col, result.val);
            if (result.est) {
                markCell(year, col);
            }
            if (result.shared) {
                markShared(year, col);
            }
        }
        for (const result of results.yearly || []) {
            annual.set(result.m, result.val);
            if (result.est) {
                estYears.add(result.m);
            }
            if (result.shared) {
                sharedYears.add(result.m);
            }
        }
    } else if (summary === "count") {
        const numericThreshold = Number(threshold);
        for (const result of results.daily || []) {
            const [year, month] = result.d;
            const colYear = seasonal ? seasonOf(year, month - 1).year : year;
            const col = seasonal ? seasonOf(year, month - 1).season : month - 1;
            ensureYear(colYear);
            if (!matrix.get(colYear).has(col)) {
                matrix.get(colYear).set(col, 0);
            }
            if (!annual.has(year)) {
                annual.set(year, 0);
            }
            if (result.val > numericThreshold) {
                matrix.get(colYear).set(col, matrix.get(colYear).get(col) + 1);
                annual.set(year, annual.get(year) + 1);
            }
            if (result.est) {
                markCell(colYear, col);
                estYears.add(year);
            }
        }
    } else {
        const rows = seasonal ? (results.seasonal || []) : (results.monthly || []);
        for (const result of rows) {
            const [year, col] = seasonal ? result.m : [result.m[0], result.m[1] - 1];
            ensureYear(year);
            matrix.get(year).set(col, result.summary[selectedSummaryKey]);
            if (result.est) {
                markCell(year, col);
            }
        }
        for (const result of results.yearly || []) {
            annual.set(result.m, result.summary[selectedSummaryKey]);
            if (result.est) {
                estYears.add(result.m);
            }
        }
    }

    return { matrix, annual, estMonths, estYears, sharedMonths, sharedYears,
        currentYear, currentMonth, response, error, isValidating };
}

function formatCell(summary, unit, value, fmat, shared = false) {
    if (value == null) {
        return "-";
    }
    if (isDayLength(summary)) {
        const text = formatSpellLength(value);
        return summary === "spells" && shared ? text + "*" : text;
    }
    return formatObs(unit, value, fmat, false, false);
}

function MonthlyMatrix({ obs, dailyAggregation, summary, threshold, est, dir, spellThreshold, period = "monthly" }) {
    const obsObj = OBS.get(obs);
    const fmat = fmatForObs(obs, dailyAggregation);
    const unit = useContext(UnitCtx);
    const seasonal = period === "seasonal";
    const columns = seasonal ? SEASONS : months;
    const { matrix, annual, estMonths, estYears, sharedMonths, sharedYears, currentYear, currentMonth, response, error, isValidating }
        = useMatrixData(obs, dailyAggregation, summary, threshold, est, dir, spellThreshold, period);
    // Rain also gets a water-year column; from October the in-progress water
    // year ends next calendar year, so it needs its own (otherwise future) row.
    const waterYears = useWaterYears(obs, summary, threshold, est,
        spellOpts(summary, dir, spellThreshold, dailyAggregation));
    const lastYear = Math.max(currentYear, waterYears?.currentWaterYear || currentYear);
    const years = Array.from(Array(lastYear - dataYearStart(est) + 1).keys())
        .map((offset) => lastYear - offset);
    // Climate comparison (as on nw3weather) only for the mean / total summary
    // of a daily series that has normals, e.g. mean of daily highs, rain total.
    const showClimate = summary === obsObj.summary && hasClimate(obs, dailyAggregation);

    const colCount = columns.length + 1 + (waterYears ? 1 : 0);
    return <Grid id="obs-monthly-matrix"
        templateColumns={"0.8fr repeat(" + colCount + ", 1fr)"}
        templateRows="30px auto"
        overflow="auto"
        marginTop="4"
        columnGap={{ base: 1, md: 2, lg: 3, xl: 5 }}
    >
        <Flex justifyContent="center" fontSize="lg">
            {isValidating && !response ? <Spinner size="sm" /> : obsObj.icon}
        </Flex>
        {columns.map((col) =>
            <Box key={col} fontWeight="bold" textAlign="center">{seasonal ? SEASON_LABELS[col] : monthNames[col]}</Box>
        )}
        <Box fontWeight="bold" textAlign="center">Annual</Box>
        {waterYears && <WaterYearHeader />}
        {years.map((year) =>
            <Box key={year} display="contents">
                <Box minW="46px" py="2" fontWeight="bold" textAlign="center">{year}</Box>
                {columns.map((col) => {
                    const isFuture = seasonal
                        ? isSeasonFuture(year, col, currentYear, currentMonth)
                        : year > currentYear || (year === currentYear && col > currentMonth);
                    const hasValue = matrix.get(year)?.has(col);
                    const value = hasValue ? matrix.get(year).get(col) : null;
                    const formattedValue = formatCell(summary, unit, value, fmat,
                        !!sharedMonths.get(year)?.has(col));
                    const { bg, col: colour } = isFuture
                        ? { bg: "gray.200", col: "black" }
                        : styleForReportValue(value, fmat, unit, summary, false, true);
                    const normal = seasonal
                        ? seasonalNormal(obs, dailyAggregation, col)
                        : monthlyNormal(obs, dailyAggregation, col + 1);

                    return <Box key={year + "-" + col}
                        className="cell"
                        textAlign="center"
                        backgroundColor={bg}
                        color={colour}
                        border="1px solid transparent"
                        _hover={hasValue ? { border: "1px solid " + colour } : {}}
                        py="2"
                        px="1"
                    >
                        {isFuture ? "" : <EstMark est={estMonths.get(year)?.has(col)}>{formattedValue}</EstMark>}
                        {showClimate && !isFuture && <ClimateAnom value={value} obs={obs} stat={dailyAggregation} unit={unit}
                            normal={normal} />}
                    </Box>;
                })}
                {(() => {
                    const hasValue = annual.has(year);
                    const value = hasValue ? annual.get(year) : null;
                    const isFuture = year > currentYear;
                    const formattedValue = isFuture ? "" : formatCell(summary, unit, value, fmat,
                        !!sharedYears.has(year));
                    const { bg, col } = isFuture
                        ? { bg: "gray.200", col: "black" }
                        : styleForReportValue(value, fmat, unit, summary, true);

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
                        {formattedValue === "" ? "" : <EstMark est={estYears.has(year)}>{formattedValue}</EstMark>}
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
        <EstNote show={isEstOn(est) && (estYears.size > 0 || [...estMonths.values()].some((s) => s.size))} gridColumn="1 / -1" />
    </Grid>;
}

function calcStats(values) {
    const items = values.map((v) => (v != null && typeof v === "object" && "value" in v) ? v : { value: v, est: false })
        .filter((v) => v.value != null && !Number.isNaN(v.value));
    if (items.length === 0) {
        return null;
    }
    const nums = items.map((v) => v.value);
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    return {
        min,
        max,
        avg: nums.reduce((a, b) => a + b, 0) / nums.length,
        n: nums.length,
        minEst: items.some((v) => v.value === min && v.est),
        maxEst: items.some((v) => v.value === max && v.est),
        avgEst: items.some((v) => v.est),
    };
}

// Per-column and annual min/max/avg across years. Years without a value are
// skipped (not counted as zero). The in-progress month or season, and the
// current year, are left out because their partial totals/means would skew
// the all-time figures.
function allTimeStats(matrix, annual, currentYear, currentMonth, estMonths, estYears, period = "monthly") {
    const seasonal = period === "seasonal";
    const columns = seasonal ? SEASONS : months;
    const byMonth = columns.map((col) => {
        const values = [];
        for (const [year, monthMap] of matrix) {
            const skip = seasonal
                ? isSeasonCurrentOrFuture(year, col, currentYear, currentMonth)
                : year === currentYear && col >= currentMonth;
            if (skip) {
                continue;
            }
            if (monthMap.has(col)) {
                values.push({ value: monthMap.get(col), est: !!estMonths?.get(year)?.has(col) });
            }
        }
        return calcStats(values);
    });

    const annualValues = [];
    for (const [year, value] of annual) {
        if (year !== currentYear) {
            annualValues.push({ value, est: !!estYears?.has(year) });
        }
    }

    return { byMonth, annual: calcStats(annualValues) };
}

function AllTimeSummary({ obs, dailyAggregation, summary, threshold, est, dir, spellThreshold, period = "monthly" }) {
    const obsObj = OBS.get(obs);
    const fmat = fmatForObs(obs, dailyAggregation);
    const unit = useContext(UnitCtx);
    const seasonal = period === "seasonal";
    const columns = seasonal ? SEASONS : months;
    const { matrix, annual, estMonths, estYears, currentYear, currentMonth, response, error, isValidating }
        = useMatrixData(obs, dailyAggregation, summary, threshold, est, dir, spellThreshold, period);
    const stats = allTimeStats(matrix, annual, currentYear, currentMonth, estMonths, estYears, period);
    // Same water-year column as the matrix (rain only), over complete water
    // years: the in-progress and any partial first water year are left out.
    const waterYears = useWaterYears(obs, summary, threshold, est,
        spellOpts(summary, dir, spellThreshold, dailyAggregation));
    const waterYearStats = waterYears ? completeWaterYearStats(waterYears.waterYears) : null;

    // Anomalies against the climate normal, same rule as the matrix (mean / total summary with normals).
    const showClimate = summary === obsObj.summary && hasClimate(obs, dailyAggregation);
    const anom = (value, normal, stat = dailyAggregation) => showClimate && value != null
        ? <ClimateAnom value={value} normal={normal} obs={obs} stat={stat} unit={unit} /> : null;

    const rows = [
        { key: "min", label: "Min" },
        { key: "max", label: "Max" },
        { key: "avg", label: "Avg" },
    ];

    const formatValue = (value, key) => {
        if (value == null) {
            return "-";
        }
        if (isDayLength(summary)) {
            return formatSpellLength(value, { average: key === "avg" });
        }
        return formatObs(unit, value, fmat, false, false);
    };

    const colCount = columns.length + 1 + (waterYears ? 1 : 0);
    return <Grid id="obs-alltime-summary"
        templateColumns={"0.8fr repeat(" + colCount + ", 1fr)"}
        templateRows="30px auto"
        overflow="auto"
        marginTop="4"
        columnGap={{ base: 1, md: 2, lg: 3, xl: 5 }}
    >
        <Flex justifyContent="center" fontSize="lg">
            {isValidating && !response ? <Spinner size="sm" /> : obsObj.icon}
        </Flex>
        {columns.map((col) =>
            <Box key={col} fontWeight="bold" textAlign="center">{seasonal ? SEASON_LABELS[col] : monthNames[col]}</Box>
        )}
        <Box fontWeight="bold" textAlign="center">Annual</Box>
        {waterYears && <WaterYearHeader />}
        {rows.map(({ key, label }) =>
            <Box key={key} display="contents">
                <Box minW="46px" py="2" fontWeight="bold" textAlign="center">{label}</Box>
                {columns.map((col, idx) => {
                    const value = stats.byMonth[idx]?.[key] ?? null;
                    const { bg, col: colour } = styleForReportValue(value, fmat, unit, summary, false, true);
                    const cellEst = key === "min" ? stats.byMonth[idx]?.minEst
                        : key === "max" ? stats.byMonth[idx]?.maxEst
                            : stats.byMonth[idx]?.avgEst;
                    const normal = seasonal
                        ? seasonalNormal(obs, dailyAggregation, col)
                        : monthlyNormal(obs, dailyAggregation, col + 1);

                    return <Box key={col + "-" + key}
                        className="cell"
                        textAlign="center"
                        backgroundColor={bg}
                        color={colour}
                        border="1px solid transparent"
                        _hover={value != null ? { border: "1px solid " + colour } : {}}
                        py="2"
                        px="1"
                    >
                        <EstMark est={cellEst}>{formatValue(value, key)}</EstMark>
                        {anom(value, normal)}
                    </Box>;
                })}
                {(() => {
                    const value = stats.annual?.[key] ?? null;
                    const { bg, col } = styleForReportValue(value, fmat, unit, summary, true);
                    const cellEst = key === "min" ? stats.annual?.minEst
                        : key === "max" ? stats.annual?.maxEst
                            : stats.annual?.avgEst;

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
                        <EstMark est={cellEst}>{formatValue(value, key)}</EstMark>
                        {anom(value, annualNormal(obs, dailyAggregation))}
                    </Box>;
                })()}
                {waterYears && (() => {
                    const entry = waterYearStats?.[key];
                    const value = entry == null ? null : key === "avg" ? entry : entry.value;
                    const { bg, col } = styleForReportValue(value, obsObj.fmat, unit, summary, true);
                    const wyEst = key === "avg"
                        ? Array.from(waterYears?.waterYears || []).some(([, info]) => info.status === "complete" && info.est)
                        : entry?.waterYear != null && !!waterYears?.waterYears.get(entry.waterYear)?.est;

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
                        <EstMark est={wyEst}>{formatValue(value, key)}</EstMark>
                        {anom(value, waterYearNormal(obs, "total"), "total")}
                    </Box>;
                })()}
            </Box>
        )}
        {error && <Text gridColumn="1 / -1" color="red.600">Unable to load summary data.</Text>}
    </Grid>;
}

// Selections kept in the URL, e.g. /reports/alltime?var=rain&summary=count&threshold=0.1
// period=seasonal is omitted when monthly (the default).
const ALLTIME_URL_STATE = {
    obs: { param: "var", def: () => "temp", valid: inList(MULTIDAY_OBS_STATES) },
    period: { def: () => "monthly", valid: inList(PERIODS) },
    // summary is resolved before daily so a Spells view can snap to a supported daily statistic.
    summary: { def: (s) => OBS.get(s.obs).summary, valid: (v, s) => allTimeSummaryOptions(s.obs).includes(v) },
    dailyAggregation: {
        param: "daily",
        def: (s) => defaultDailyFor(s.obs, s.summary),
        valid: (v, s) => s.summary === "spells" ? hasSpellOptions(s.obs, v) : dailyAggregationOptions(s.obs).includes(v),
    },
    threshold: {
        def: () => "0", valid: (v, s) => countThresholdsAny(s.obs).includes(v), use: (s) => s.summary === "count",
    },
    dir: { def: () => "above", valid: inList(["above", "below"]), use: (s) => s.summary === "spells" },
    spellThreshold: {
        param: "level",
        def: (s) => spellDefaultThreshold(s.obs, s.dailyAggregation) || "0",
        valid: (v, s) => spellThresholdsAny(s.obs, s.dailyAggregation).includes(v),
        use: (s) => s.summary === "spells",
    },
    est: { def: () => "0", valid: (v) => v === "0" || v === "1" },
};

function AllTimeHeading({ obs, dailyAggregation, summary, dir, spellThreshold }) {
    const unit = useContext(UnitCtx);
    if (summary === "spells") {
        return spellSummaryLabel(obs, dailyAggregation, dir, spellThreshold, unit)
            + " – " + OBS.get(obs).name;
    }
    return SUMMARY_NAMES[summary] + " of " + dailyAggName(obs, dailyAggregation) + " " + OBS.get(obs).name;
}

export default function AllTimeReport() {
    const [{ obs, dailyAggregation, summary, threshold, est, dir, spellThreshold, period }, update] = useUrlState(ALLTIME_URL_STATE);
    const monthlySummaryOptions = allTimeSummaryOptions(obs);
    const seasonal = period === "seasonal";

    // Switching variable resets the daily statistic and threshold; a Mean/Total
    // summary follows the new variable (Min/Max/Count are kept). Spells is kept
    // when the new variable has spell options.
    const handleObsChange = (nextObs, nextStat) => {
        const keepSpells = summary === "spells" && SPELL_OBS.includes(nextObs);
        let nextDaily = nextStat || defaultDailyFor(nextObs, keepSpells ? "spells" : summary);
        if (keepSpells && !hasSpellOptions(nextObs, nextDaily)) {
            nextDaily = spellDailyStats(nextObs)[0] || nextDaily;
        }
        update({
            obs: nextObs,
            dailyAggregation: nextDaily,
            threshold: "0",
            summary: keepSpells ? "spells"
                : (isTotalObs(nextObs) || summary === "avg" || summary === "total" ? OBS.get(nextObs).summary : summary),
            spellThreshold: spellDefaultThreshold(nextObs, nextDaily) || spellThreshold,
        });
    };
    const setDailyAggregation = (value) => update({
        dailyAggregation: value,
        ...(summary === "spells" ? { spellThreshold: spellDefaultThreshold(obs, value) } : {}),
    });
    const setSummary = (value) => {
        const nextDaily = value === "spells" && !hasSpellOptions(obs, dailyAggregation)
            ? (spellDailyStats(obs)[0] || dailyAggregation)
            : dailyAggregation;
        update({
            summary: value,
            dailyAggregation: nextDaily,
            ...(value === "spells" ? { spellThreshold: spellDefaultThreshold(obs, nextDaily) } : {}),
        });
    };
    const setThreshold = (value) => update({ threshold: value });
    const setDir = (value) => update({ dir: value });
    const setSpellThreshold = (value) => update({ spellThreshold: value });
    const setPeriod = (value) => update({ period: value });

    return <Page name="reports" sub="all-time" title="Reports | all-time">
        <Heading as="h1" size="1">Reports: All-time</Heading>
        <Heading as="h2" size="2">
            <AllTimeHeading obs={obs} dailyAggregation={dailyAggregation} summary={summary}
                dir={dir} spellThreshold={spellThreshold} />
        </Heading>
        <ClimateNormalsLink />

        <Text fontWeight="bold">Variable:</Text>
        <RadioButtonGroup name="obs" value={baseObs(obs)}
            options={summary === "spells" ? DAILY_VALUE_OBS_OPTIONS.filter((v) => SPELL_OBS.includes(v)) : DAILY_VALUE_OBS_OPTIONS}
            optFormat={fmatObsOpt} fn={handleObsChange} />
        <SunViewToggle obs={obs} stat={dailyAggregation} fn={handleObsChange} multiDay />
        <StatButtons name="daily-aggregation" label="Daily statistic:" obs={obs} stat={dailyAggregation}
            options={summary === "spells"
                ? (o) => dailyAggregationOptions(o).filter((s) => hasSpellOptions(o, s))
                : dailyAggregationOptions}
            optFormat={(value) => DAILY_AGGREGATION_NAMES[value]} fn={setDailyAggregation} onObs={handleObsChange}
            allowObs={(v) => summary === "spells" ? SPELL_OBS.includes(v) : MULTIDAY_OBS_STATES.includes(v)} />
        <Text mt="1" fontWeight="bold">Period:</Text>
        <RadioButtonGroup name="period" value={period} options={PERIODS} optFormat={(value) => PERIOD_LABELS[value]} fn={setPeriod} />
        <Text mt="1" fontWeight="bold">Summary:</Text>
        <RadioButtonGroup name="summary" value={summary} options={monthlySummaryOptions} optFormat={(value) => SUMMARY_NAMES[value]} fn={setSummary} />
        {summary === "count" && <CountThresholdSelector obs={obs} value={threshold} fn={setThreshold} />}
        {summary === "spells" && <>
            <SpellKindSelector obs={obs} dir={dir} fn={setDir} />
            <SpellThresholdSelector obs={obs} dailyAggregation={dailyAggregation} value={spellThreshold} fn={setSpellThreshold} />
        </>}
        <EstToggle value={est} onChange={(v) => update({ est: v })} />

        <MonthlyMatrix obs={obs} dailyAggregation={dailyAggregation} summary={summary} threshold={threshold} est={est}
            dir={dir} spellThreshold={spellThreshold} period={period} />

        <Heading as="h3" size="3" mt="6">Min, max and average across all years</Heading>
        <AllTimeSummary obs={obs} dailyAggregation={dailyAggregation} summary={summary} threshold={threshold} est={est}
            dir={dir} spellThreshold={spellThreshold} period={period} />

        {summary === "spells" ? <>
            <Text mt="3">
                Each spell has one main period of each kind (month or season, calendar year, water year): the period
                it overlaps the most, with ties broken by the period that contains its midpoint (the earlier
                middle day when the length is even). In that main period the cell shows the spell's full
                length. In every other period the spell touches, only the days that fall inside that period
                are counted. The cell value is the longest of those candidate lengths. A period with
                observations but no such spell is 0. A missing day ends the spell, as on the spells ranking.
                An ongoing spell, still running on the latest eligible day, is counted at its length so far.
                Rain and wet hours may include today; temperatures and sunshine stop at yesterday.
                {seasonal && " Seasons are meteorological: Winter is December–February, labelled by the year"
                    + " that contains January (so December is included in the following year's Winter);"
                    + " Spring is March–May; Summer is June–August; Autumn (Fall) is September–November."}
            </Text>
            <Text mt="2">
                * spell crosses a period boundary (shown at full length in its main period, truncated elsewhere).
            </Text>
            <Text mt="2">
                The table above compares the same {seasonal ? "season" : "month"} (or full year) across years: its min, max and average
                are taken over the spell lengths in the matrix. Years with no data for a {seasonal ? "season" : "month"} are ignored
                rather than counted as zero. The current, still in-progress {seasonal ? "season" : "month"} and year are excluded so
                partial spells do not skew the results; for rain, the Water yr column likewise covers complete
                water years only (in-progress and partial water years are excluded).
            </Text>
        </> : <>
            <Text mt="3">
                Choose a daily series first, then summarize those daily values independently for each
                {" "}{seasonal ? "season" : "month"} and year.
                Count is the number of selected daily values above the chosen threshold. Rainfall uses daily totals.
                {seasonal && " Seasons are meteorological: Winter is December–February, labelled by the year"
                    + " that contains January (so December is included in the following year's Winter);"
                    + " Spring is March–May; Summer is June–August; Autumn (Fall) is September–November."}
            </Text>
            <Text mt="2">
                The table above compares the same {seasonal ? "season" : "month"} (or full year) across years: its min, max and average are
                taken over the values in the matrix. Years with no data for a {seasonal ? "season" : "month"} are ignored rather than counted as
                zero. The current, still in-progress {seasonal ? "season" : "month"} and year are excluded so partial data does not skew the results;
                for rain, the Water yr column likewise covers complete water years only (in-progress and partial
                water years are excluded).
            </Text>
        </>}
      <DerivedVarNote obs={obs} mt="3" />
    </Page>;
}
