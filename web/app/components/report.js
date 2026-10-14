import { Box, Flex, Text, useRadioGroup } from "@chakra-ui/react";
import { useContext } from "react";
import { convFunction, formatObs, scaleForObsType } from "../format";
import { baseObs, dailyStatsFor, OBS, VIEW_GROUPS } from "./conf";
import { UnitCtx } from "./Page";
import RadioCard from "./RadioCard";

export const REPORT_YEAR_START = 2021;

// Variables with minute observations (daily report graphs).
export const REPORT_OBS_OPTIONS = [
    "temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt", "gust", "sun",
];

// Variables with daily values (rankings, all-time). "sun" is already in REPORT_OBS_OPTIONS (added in #28).
export const DAILY_VALUE_OBS_OPTIONS = REPORT_OBS_OPTIONS;

// Every value the "var" URL parameter may take: the buttons plus alternative views (sunshine as %).
export const DAILY_VALUE_OBS_STATES = [...DAILY_VALUE_OBS_OPTIONS, "sunpct", "wet", "wetrate", "rain60", "rain10"];

export const COUNT_THRESHOLDS = {
    temp: ["0", "5", "10", "15", "20", "25", "30", "35"],
    wind: ["0", "5", "10", "15", "20", "25"],
    humi: ["0", "40", "50", "60", "70", "80", "90"],
    pres: ["0", "1000", "1010", "1020", "1030"],
    aqi: ["0", "50", "100", "150", "200"],
    rain: ["0", "0.01", "0.1", "0.25", "0.5", "1"],
    wdir: ["0", "45", "90", "135", "180", "225", "270", "315"],
    dewpt: ["0", "5", "10", "15", "20", "25"],
    gust: ["0", "10", "20", "30", "40"],
    sun: ["0", "1", "4", "8", "10"],
    sunpct: ["0", "25", "50", "75", "90"],
    wet: ["0", "1", "3", "6", "12"],
    wetrate: ["0", "0.02", "0.05", "0.1", "0.2"],
    rain60: ["0", "0.05", "0.1", "0.25", "0.5"],
    rain10: ["0", "0.02", "0.05", "0.1", "0.2"],
};

export const SUMMARY_NAMES = {
    min: "Minimum",
    max: "Maximum",
    avg: "Mean",
    total: "Total",
    count: "Count",
};

export const DAILY_AGGREGATION_NAMES = {
    min: "Daily Low",
    max: "Daily High",
    avg: "Daily Mean",
    total: "Daily Total",
};

export function dailyAggregationOptions(obs) {
    return dailyStatsFor(obs);
}

export function summaryOptions(obs) {
    // Variables summarised by their max (e.g. max 10-/60-min rain) would otherwise list "max" twice.
    return [...new Set(["min", "max", OBS.get(obs).summary, "count"])];
}

export function summaryKey(summary) {
    if (summary === "min") {
        return "min_val";
    }
    if (summary === "max") {
        return "max_val";
    }
    return summary;
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
        col: i > 5 ? "white" : "black",
    };
}

// `monthly`: the value aggregates a month (annual=true: a year), so variables with period scales use them.
export function styleForReportValue(value, obsType, unit, summary, annual = false, monthly = false) {
    if (summary === "count") {
        const scale = annual
            ? [1, 50, 100, 150, 200, 250, 300, 365]
            : [1, 5, 10, 15, 20, 25, 28, 31];
        return styleForScaleValue(value, scale);
    }
    const convertedValue = value == null ? null : convFunction(unit, obsType)(value);
    const period = annual ? "year" : monthly ? "month" : "day";
    return styleForScaleValue(convertedValue, scaleForObsType(unit, obsType, period, summary));
}

export function RadioButtonGroup(props) {
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

export function CountThresholdSelector({ obs, value, fn }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);

    return <Box mt="1">
        <Text fontWeight="bold">Count days greater than:</Text>
        <RadioButtonGroup
            name="threshold"
            value={value}
            options={COUNT_THRESHOLDS[obs]}
            optFormat={(threshold) => formatObs(unit, Number(threshold), obsObj.fmat)}
            fn={fn}
        />
    </Box>;
}

// Views of one variable button, shown under the Variable buttons while it is selected:
// "Show sunshine as: Hours | % of possible", "Show rainfall as: Amount | Wet hours".
export function SunViewToggle({ obs, fn, Group = RadioButtonGroup }) {
    const base = baseObs(obs);
    const g = VIEW_GROUPS[base];
    if (!g) {
        return null;
    }
    return <>
        <Text mt="1" fontWeight="bold">{g.label}</Text>
        <Group name={base + "-view"} value={obs} options={g.views} optFormat={(v) => g.names[v]} fn={fn} />
    </>;
}
