import { Box, Flex, Grid, Heading, Spinner, Text, useRadioGroup } from "@chakra-ui/react";
import { useContext, useState } from "react";
import useSWR from "swr";
import { fetcher, fmatObsOpt, OBS } from "../../components/conf";
import { Page, UnitCtx } from "../../components/Page";
import RadioCard from "../../components/RadioCard";
import { convFunction, formatObs, scaleForObsType } from "../../format";

const yearStart = 2020;
const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const months = Array.from(Array(12).keys());

const summaryNames = {
    min: "Minimum",
    max: "Maximum",
    avg: "Mean",
    total: "Total",
    count: "Count",
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

function styleForValue(value, obsType, unit, summary) {
    if (summary === "count") {
        return styleForScaleValue(value, [1, 5, 10, 15, 20, 25, 28, 31]);
    }
    const convertedValue = value == null ? null : convFunction(unit, obsType)(value);
    return styleForScaleValue(convertedValue, scaleForObsType(unit, obsType));
}

function useMonthlySummaries(obs, summary) {
    // Each selected summary uses the matching daily series. Count uses the
    // variable's canonical series so it represents days with usable data.
    // Rain is cumulative during a day, so all of its monthly statistics must
    // be derived from daily totals rather than intraday readings.
    const dailyAggregation = obs === "rain"
        ? "total"
        : (summary === "count" ? OBS.get(obs).summary : summary);
    const url = "/api/var/monthly/" + obs + "/" + dailyAggregation
        + "/?start=" + yearStart + "0101&include_today=1";
    return useSWR(url, fetcher, { refreshInterval: 300000 });
}

function MonthlyMatrix({ obs, summary }) {
    const obsObj = OBS.get(obs);
    const unit = useContext(UnitCtx);
    const { data: response, error, isValidating } = useMonthlySummaries(obs, summary);
    const results = response?.result || [];
    const serverDate = response?.server?.date || [new Date().getFullYear(), new Date().getMonth() + 1, 1];
    const currentYear = serverDate[0];
    const currentMonth = serverDate[1] - 1;
    const years = Array.from(Array(currentYear - yearStart + 1).keys())
        .map((offset) => currentYear - offset);
    const summaryKey = summary === "min" ? "min_val" : summary === "max" ? "max_val" : summary;

    const matrix = new Map();
    for (const result of results) {
        const [year, month] = result.m;
        if (!matrix.has(year)) {
            matrix.set(year, new Map());
        }
        matrix.get(year).set(month - 1, result.summary[summaryKey]);
    }

    return <Grid id="obs-monthly-matrix"
        templateColumns="0.8fr repeat(12, 1fr)"
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
        {years.map((year) =>
            <Box key={year} display="contents" sx={{ ":hover > div": { backgroundColor: "gray.400" } }}>
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
            </Box>
        )}
        {error && <Text gridColumn="1 / -1" color="red.600">Unable to load monthly data.</Text>}
    </Grid>;
}

export default function MonthlyReport() {
    const [obs, setObs] = useState("temp");
    const [summary, setSummary] = useState("avg");
    const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt", "gust"];
    const summaryOptions = ["min", "max", OBS.get(obs).summary, "count"];

    const handleObsChange = (nextObs) => {
        setObs(nextObs);
        const nextMiddleSummary = OBS.get(nextObs).summary;
        if (summary === "avg" || summary === "total") {
            setSummary(nextMiddleSummary);
        }
    };

    return <Page name="reports" sub="monthly" title="Reports | monthly matrix">
        <Heading as="h1" size="1">Reports: Monthly matrix</Heading>
        <Heading as="h2" size="2">
            Monthly {summaryNames[summary]} {OBS.get(obs).name}
        </Heading>

        <RadioButtonGroup name="obs" value={obs} options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
        <RadioButtonGroup name="summary" value={summary} options={summaryOptions} optFormat={(value) => summaryNames[value]} fn={setSummary} />

        <MonthlyMatrix obs={obs} summary={summary} />

        <Text mt="3">
            Each row is a year and each column is a month. Minimum and maximum use daily extremes,
            mean uses daily means, and count is the number of days represented. Rainfall statistics use daily totals.
        </Text>
    </Page>;
}
