import { Box, Flex, Text, useRadioGroup } from "@chakra-ui/react";
import { useContext, useEffect } from "react";
import { convFunction, formatObs, scaleForObsType } from "../format";
import { baseObs, dailyStatsFor, OBS, VIEW_GROUPS } from "./conf";
import { UnitCtx } from "./Page";
import RadioCard from "./RadioCard";

export const REPORT_YEAR_START = 2021;

// Unit conversion helpers for threshold options (stored in DB base units: °C, inches, mph, mb).
export const cToF = (c) => String(c * 9 / 5 + 32);
export const fToC = (f) => String(Math.round((f - 32) * 5 / 9 * 10000) / 10000);
export const mmToIn = (mm) => String(Math.round(mm / 25.4 * 10000) / 10000);
export const kphToMph = (kph) => String(Math.round(kph / 1.60934 * 10000) / 10000);
export const inHgToMb = (inhg) => String(Math.round(inhg / 0.02953 * 100) / 100);

// Closest option for the current unit, so switching units keeps a similar threshold (e.g. 0.1 in -> 2 mm, 90 °F -> 30 °C).
export function nearestThreshold(value, options) {
    if (!options.length || options.includes(value)) {
        return value;
    }
    return options.reduce((best, o) => Math.abs(Number(o) - Number(value)) < Math.abs(Number(best) - Number(value)) ? o : best);
}

// Variables with minute observations (daily report graphs, latest charts).
export const REPORT_OBS_OPTIONS = [
    "temp", "rain", "humi", "dewpt", "aqi", "wind", "pres",
];

export const MINUTE_OBS_STATES = [...REPORT_OBS_OPTIONS, "gust", "wdir"];

// Variables with daily values (rankings, all-time, matrix, summary, year charts).
export const DAILY_VALUE_OBS_OPTIONS = [
    "temp", "rain", "sun", "humi", "dewpt", "aqi", "wind", "pres",
];

// Every value the "var" URL parameter may take: the buttons plus alternative views (sunshine as %, rain views, wind views).
export const DAILY_VALUE_OBS_STATES = [...DAILY_VALUE_OBS_OPTIONS, "sunpct", "fog", "fogday", "wet", "wetrate", "rain60", "rain10", "gust", "wdir"];

// Wind direction is circular: a day's mean direction is shown, but it is never averaged over several days
// (monthly / annual summaries, multi-day means, spells), matching DAILY_ONLY_VARS in rwcwx/calc/avg_extreme.py.
export const DAILY_ONLY_OBS = ["wdir"];
export const MULTIDAY_OBS_STATES = DAILY_VALUE_OBS_STATES.filter((o) => !DAILY_ONLY_OBS.includes(o));

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
    fog: ["0", "0.5", "1", "2", "3"],
    fogday: ["0"],
    wet: ["0", "1", "3", "6", "12"],
    wetrate: ["0", "0.02", "0.05", "0.1", "0.2"],
    rain60: ["0", "0.05", "0.1", "0.25", "0.5"],
    rain10: ["0", "0.02", "0.05", "0.1", "0.2"],
};

// Metric (uk & eu) count thresholds for variables stored in imperial units (rainfall in inches, rain rate in in/h).
const COUNT_THRESHOLDS_METRIC = {
    rain: ["0", "0.01", ...[2, 5, 10, 25].map(mmToIn)],
    wetrate: ["0", ...[0.5, 1, 2, 5].map(mmToIn)],
    rain60: ["0", ...[1, 2, 5, 10].map(mmToIn)],
    rain10: ["0", ...[0.5, 1, 2, 5].map(mmToIn)],
};

// EU count thresholds for wind/gust (displayed in kph, stored in mph).
const COUNT_THRESHOLDS_EU = {
    wind: ["0", ...[10, 15, 20, 30, 40].map(kphToMph)],
    gust: ["0", ...[15, 30, 45, 60].map(kphToMph)],
};

// US count thresholds for variables stored in metric units (temp/dewpt in °C, pres in mb; 0 °C = 32 °F).
const COUNT_THRESHOLDS_US = {
    temp: ["0", ...[40, 50, 60, 70, 80, 90, 100].map(fToC)],
    dewpt: ["0", ...[40, 45, 50, 55, 60, 65].map(fToC)],
    pres: ["0", ...[29.6, 29.8, 30.0, 30.2, 30.4].map(inHgToMb)],
};

export function countThresholds(obs, unit = "us") {
    if (unit === "eu" && COUNT_THRESHOLDS_EU[obs]) {
        return COUNT_THRESHOLDS_EU[obs];
    }
    if (unit !== "us" && COUNT_THRESHOLDS_METRIC[obs]) {
        return COUNT_THRESHOLDS_METRIC[obs];
    }
    if (unit === "us" && COUNT_THRESHOLDS_US[obs]) {
        return COUNT_THRESHOLDS_US[obs];
    }
    return COUNT_THRESHOLDS[obs] || [];
}

export function countThresholdsAny(obs) {
    return [...new Set([
        ...countThresholds(obs, "us"),
        ...countThresholds(obs, "uk"),
        ...countThresholds(obs, "eu"),
    ])];
}

export function formatCountThreshold(unit, obs, threshold) {
    const num = Number(threshold);
    if (obs === "rain" && (num === 0.01 || num === 0.0079) && unit !== "us") {
        return "0.2 mm";
    }
    const fmat = OBS.get(obs).fmat;
    const raw = formatObs(unit, num, fmat);
    return unit === "us" && (fmat === "rain" || fmat === "wetrate" || fmat === "pres") && num !== 0
        ? raw
        : raw.replace(/\.0+(?=\s|$)/, "");
}

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
    const options = countThresholds(obs, unit);
    const nearest = nearestThreshold(value, options);

    useEffect(() => {
        if (nearest !== value) {
            fn(nearest);
        }
    }, [nearest, value]);  // eslint-disable-line react-hooks/exhaustive-deps

    return <Box mt="1">
        <Text fontWeight="bold">Count days greater than:</Text>
        <RadioButtonGroup
            name="threshold"
            value={value}
            options={options}
            optFormat={(threshold) => formatCountThreshold(unit, obs, threshold)}
            fn={fn}
        />
    </Box>;
}

// Views of one variable button, shown under the Variable buttons while it is selected:
// "Show sunshine as: Hours | % of possible", "Show rainfall as: Amount | Wet hours",
// "Show wind as: Max speed | Max gust | Avg speed | Avg gust | Avg direction" (or minute-level wind views).
// multiDay: the page summarises several days, so daily-only views (wind direction) are left out.
export function SunViewToggle({ obs, stat, fn, Group = RadioButtonGroup, summaryMode = true, multiDay = false }) {
    const base = baseObs(obs);
    const g = VIEW_GROUPS[base];
    if (!g) {
        return null;
    }
    if (base === "wind" && summaryMode) {
        const effStat = stat || (obs === "wdir" ? "avg" : "max");
        const views = multiDay ? g.summaryViews.filter((v) => !DAILY_ONLY_OBS.includes(v.split(":")[0])) : g.summaryViews;
        const val = views.includes(obs + ":" + effStat) ? obs + ":" + effStat : "wind:max";
        return <>
            <Text mt="1" fontWeight="bold">{g.label}</Text>
            <Group
                name="wind-view"
                value={val}
                options={views}
                optFormat={(v) => g.summaryNames[v]}
                fn={(v) => {
                    const [nextObs, nextStat] = v.split(":");
                    fn(nextObs, nextStat);
                }}
            />
        </>;
    }
    return <>
        <Text mt="1" fontWeight="bold">{g.label}</Text>
        <Group name={base + "-view"} value={obs} options={g.views} optFormat={(v) => g.names[v]} fn={(v) => fn(v)} />
    </>;
}
