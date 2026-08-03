import { Box, Flex, Grid, Heading, Spinner, Text, useRadioGroup } from "@chakra-ui/react";
import { useContext, useState } from "react";
import useSWR from "swr";
import { fetcher, fmatObsOpt, OBS } from "../../components/conf";
import { Page, UnitCtx } from "../../components/Page";
import RadioCard from "../../components/RadioCard";
import { convFunction, formatObs, scaleForObsType } from "../../format";

const yearStart = 2021;
const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const months = Array.from(Array(12).keys());

const countThresholds = {
    temp: ["0", "5", "10", "15", "20", "25", "30", "35"],
    wind: ["0", "5", "10", "15", "20", "25"],
    humi: ["0", "40", "50", "60", "70", "80", "90"],
    pres: ["0", "1000", "1010", "1020", "1030"],
    aqi: ["0", "50", "100", "150", "200"],
    rain: ["0", "0.01", "0.1", "0.25", "0.5", "1"],
    wdir: ["0", "45", "90", "135", "180", "225", "270", "315"],
    dewpt: ["0", "5", "10", "15", "20", "25"],
    gust: ["0", "10", "20", "30", "40"],
};

const summaryNames = {
    min: "Minimum",
    max: "Maximum",
    avg: "Mean",
    total: "Total",
    count: "Count",
};

const dailyAggregationNames = {
    min: "Daily Low",
    max: "Daily High",
    avg: "Daily Mean",
    total: "Daily Total",
};

function RadioButtonGroup(props) {
    const { getRootProps, getRadioProps } = useRadioGroup({
        name: props.name,
        value: props.value,
        onChange: props.fn,
    });
    const group = getRootProps();

    return <Flex wrap="wrap" py="1" id={props.name} {...group}>
        {props.options.map((value) => {
            const radio = getRadioProps({ value });
            return <RadioCard key={value} {...radio}>
                {props.optFormat(value)}
            </RadioCard>;
        })}
    </Flex>;
}

function CountThresholdSelector({ obs, value, fn }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);

    return <Box mt="1">
        <Text fontWeight="bold">Count days greater than:</Text>
        <RadioButtonGroup
            name="threshold"
            value={value}
            options={countThresholds[obs]}
            optFormat={(threshold) => formatObs(unit, Number(threshold), obsObj.fmat)}
            fn={fn}
        />
    </Box>;
}

function styleForScaleValue(value, scale) {
    if (value == null) {
        return { bg: "gray.300", col: "black" };
    }

    let i = 0;
    while (i < scale.length && value >= scale[i]) {
        i++;
    }
    return {
        bg: "brand." + ((i === 0) ? 50 : i * 100).toString(),
        col: (i > 5) ? "white" : "black",
    };
}

function styleForValue(value, obsType, unit, summary, annual = false) {
    if (summary === "count") {
        const scale = annual
            ? [1, 50, 100, 150, 200, 250, 300, 365]
            : [1, 5, 10, 15, 20, 25, 28, 31];
        return styleForScaleValue(value, scale);
    }
    const convertedValue = value == null ? null : convFunction(unit, obsType)(value);
    return styleForScaleValue(convertedValue, scaleForObsType(unit, obsType));
}

function useSummaries(obs, dailyAggregation) {
    const url = "/api/var/all_periods/" + obs + "/" + dailyAggregation
        + "/?start=" + yearStart + "0101&include_today=1";
    return useSWR(url, fetcher, { refreshInterval: 300000 });
}

function MonthlyMatrix({ obs, dailyAggregation, summary, threshold }) {
    const obsObj = OBS.get(obs);
    const unit = useContext(UnitCtx);
    const { data: response, error, isValidating } = useSummaries(obs, dailyAggregation);
    const results = response?.result || {};
    const serverDate = response?.server?.date || [new Date().getFullYear(), new Date().getMonth() + 1, 1];
    const currentYear = serverDate[0];
    const currentMonth = serverDate[1] - 1;
    const years = Array.from(Array(currentYear - yearStart + 1).keys())
        .map((offset) => currentYear - offset);
    const summaryKey = summary === "min" ? "min_val" : summary === "max" ? "max_val" : summary;

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
            matrix.get(year).set(month - 1, result.summary[summaryKey]);
        }
        for (const result of results.yearly || []) {
            annual.set(result.m, result.summary[summaryKey]);
        }
    }

    return <Grid id="obs-monthly-matrix"
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
        {years.map((year) =>
            <Box key={year} display="contents">
                <Box minW="46px" py="2" fontWeight="bold" textAlign="center">{year}</Box>
                {months.map((month) => {
                    const isFuture = year === currentYear && month > currentMonth;
                    const hasValue = matrix.get(year)?.has(month);
                    const value = hasValue ? matrix.get(year).get(month) : null;
                    const formattedValue = summary === "count"
                        ? (value == null ? "-" : value.toString())
                        : formatObs(unit, value, obsObj.fmat, false, false);
                    const { bg, col } = isFuture
                        ? { bg: "gray.200", col: "black" }
                        : styleForValue(value, obsObj.fmat, unit, summary);

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
                    const formattedValue = summary === "count"
                        ? (value == null ? "-" : value.toString())
                        : formatObs(unit, value, obsObj.fmat, false, false);
                    const { bg, col } = styleForValue(value, obsObj.fmat, unit, summary, true);

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
            </Box>
        )}
        {error && <Text gridColumn="1 / -1" color="red.600">Unable to load monthly data.</Text>}
    </Grid>;
}

export default function MonthlyReport() {
    const [obs, setObs] = useState("temp");
    const [dailyAggregation, setDailyAggregation] = useState("avg");
    const [summary, setSummary] = useState("avg");
    const [threshold, setThreshold] = useState("0");
    const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt", "gust"];
    const dailyAggregationOptions = obs === "rain" ? ["total"] : ["min", "max", "avg"];
    const summaryOptions = ["min", "max", OBS.get(obs).summary, "count"];

    const handleObsChange = (nextObs) => {
        setObs(nextObs);
        setDailyAggregation(OBS.get(nextObs).summary);
        setThreshold("0");
        const nextMiddleSummary = OBS.get(nextObs).summary;
        if (summary === "avg" || summary === "total") {
            setSummary(nextMiddleSummary);
        }
    };

    return <Page name="reports" sub="monthly" title="Reports | monthly matrix">
        <Heading as="h1" size="1">Reports: Monthly matrix</Heading>
        <Heading as="h2" size="2">
            {summaryNames[summary]} of {dailyAggregationNames[dailyAggregation]} {OBS.get(obs).name}
        </Heading>

        <Text fontWeight="bold">Variable:</Text>
        <RadioButtonGroup name="obs" value={obs} options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
        <Text mt="1" fontWeight="bold">Daily statistic:</Text>
        <RadioButtonGroup
            name="daily-aggregation"
            value={dailyAggregation}
            options={dailyAggregationOptions}
            optFormat={(value) => dailyAggregationNames[value]}
            fn={setDailyAggregation}
        />
        <Text mt="1" fontWeight="bold">Monthly and annual summary:</Text>
        <RadioButtonGroup name="summary" value={summary} options={summaryOptions} optFormat={(value) => summaryNames[value]} fn={setSummary} />
        {summary === "count" && <CountThresholdSelector obs={obs} value={threshold} fn={setThreshold} />}

        <MonthlyMatrix obs={obs} dailyAggregation={dailyAggregation} summary={summary} threshold={threshold} />

        <Text mt="3">
            Choose a daily series first, then summarize those daily values independently for each month and year.
            Count is the number of selected daily values above the chosen threshold. Rainfall uses daily totals.
        </Text>
    </Page>;
}
