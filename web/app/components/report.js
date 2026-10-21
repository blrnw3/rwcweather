import { Box, Flex, Text, useRadioGroup } from "@chakra-ui/react";
import { useContext, useEffect } from "react";
import { convFunction, formatObs, scaleForObsType } from "../format";
import { baseObs, DERIVED_PARENT, DERIVED_STATS, dailyStatsFor, OBS, statButtonValue, VIEW_GROUPS } from "./conf";
import { UnitCtx } from "./Page";
import RadioCard from "./RadioCard";

export const REPORT_YEAR_START = 2021;

// Unit conversion helpers for threshold options (stored in DB base units: °C, inches, mph, mb).
export const cToF = (c) => String(c * 9 / 5 + 32);
export const fToC = (f) => String(Math.round((f - 32) * 5 / 9 * 10000) / 10000);
export const mmToIn = (mm) => String(Math.round(mm / 25.4 * 10000) / 10000);
export const kphToMph = (kph) => String(Math.round(kph / 1.60934 * 10000) / 10000);
export const inHgToMb = (inhg) => String(Math.round(inhg / 0.02953 * 100) / 100);
export const fDiffToC = (f) => String(Math.round(f * 5 / 9 * 10000) / 10000);
export const inToMm = (i) => String(Math.round(i * 25.4 * 10000) / 10000);

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
export const DAILY_VALUE_OBS_STATES = [...DAILY_VALUE_OBS_OPTIONS, "sunpct", "fog", "fogday", "wet", "wetrate", "rain60", "rain10", "gust", "wdir",
    "temprange", "et0", "humirange", "dewptrange", "presrange"];

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
    // derived: ranges in °C / % / mb, ET0 in mm
    temprange: ["0", "5", "10", "15", "20"],
    dewptrange: ["0", "3", "5", "8", "10"],
    humirange: ["0", "20", "30", "40", "50", "60"],
    presrange: ["0", "2", "4", "6", "8"],
    et0: ["0", "1", "2", "3", "4", "5", "6"],
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
    temprange: ["0", ...[10, 20, 25, 30, 35].map(fDiffToC)],
    dewptrange: ["0", ...[5, 10, 15, 20].map(fDiffToC)],
    presrange: ["0", ...[0.05, 0.1, 0.15, 0.2, 0.25].map(inHgToMb)],
    et0: ["0", ...[0.04, 0.08, 0.12, 0.16, 0.2, 0.24].map(inToMm)],
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
    range: "Daily Range",
    et0: "ET0",
};

// "Daily High" etc.; just "Daily" for derived daily variables (one value per day, named by the variable itself).
export function dailyAggName(obs, stat) {
    return DERIVED_PARENT[obs] ? "Daily" : DAILY_AGGREGATION_NAMES[stat];
}

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

// Footnote for the derived daily variables (ranges, ET0): how they are computed.
export function DerivedVarNote({ obs, ...props }) {
    if (obs === "et0") {
        return <Text fontSize="sm" {...props}>
            ET0 is the FAO-56 grass reference evapotranspiration, from the daily values: Penman-Monteith (FAO-56 eq. 6)
            with solar radiation from the webcam sunshine hours (Angström, 0.25 + 0.50 n/N), net radiation with albedo
            0.23, vapour pressure from the mean dew point, pressure from the 125 m elevation, G = 0, and the measured
            daily mean wind taken as the 2 m wind (the anemometer is above the roofline on a sheltered hillside, so no
            height reduction; floored at FAO&apos;s 0.5 m/s). Days without usable sunshine (before Sept 2021, gaps,
            under 75% webcam coverage or weather-API estimates) use Hargreaves-Samani from the max and min temperature
            instead, calibrated to Penman-Monteith month by month (each calendar month&apos;s ratio of Penman-Monteith to
            Hargreaves-Samani over all the days that have both, about 0.7 in winter to 0.88 in summer); each day&apos;s
            method is shown in the chart tooltips. Today is not included.
        </Text>;
    }
    if (OBS.get(obs)?.fmat && ["temprange", "humirange", "presrange", "dewptrange"].includes(obs)) {
        return <Text fontSize="sm" {...props}>
            {OBS.get(obs).name}: each day&apos;s maximum minus minimum (same local day as the other daily values); monthly
            and annual figures average the daily ranges. There are no climate normals for it.
        </Text>;
    }
    return null;
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

// Views of one variable button, as an unlabelled button row under the Variable buttons while it is selected:
// sunshine "Hours | % of possible | Fog hours | Fog days", rainfall "Amount | Wet hours | ...",
// wind "Max speed | Max gust | Avg speed | Avg gust | Avg direction" (or minute-level wind views).
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
        <Group name={base + "-view"} value={obs} options={g.views} optFormat={(v) => g.names[v]} fn={(v) => fn(v)} />
    </>;
}

// Daily-stat buttons of a variable plus its derived daily variables as extra stats
// (Temperature: Maximum | Minimum | Average | Range | ET0; Humidity, Dew point, Pressure: ... | Range).
// options(o): the page's own stats for a variable; allowObs(v): whether the page can show a derived variable.
// Picking a real stat calls fn(stat) (switching back to the parent variable if a derived one is shown);
// picking Range / ET0 calls onObs(derivedVar).
export function StatButtons({ obs, stat, options, fn, onObs, optFormat, name = "stat", label = null, allowObs = () => true, Group = RadioButtonGroup }) {
    const parent = DERIVED_PARENT[obs] || obs;
    const real = options(parent);
    const extras = (DERIVED_STATS[parent] || []).filter(([, v]) => allowObs(v));
    const opts = [...real, ...extras.map(([k]) => k)];
    if (baseObs(obs) === "wind" || opts.length < 2) {
        return null;
    }
    const pick = (v) => {
        const hit = extras.find(([k]) => k === v);
        if (hit) {
            onObs(hit[1]);
        } else if (parent !== obs) {
            onObs(parent, v);
        } else {
            fn(v);
        }
    };
    return <>
        {label && <Text mt="1" fontWeight="bold">{label}</Text>}
        <Group name={name} value={statButtonValue(obs, stat)} options={opts} optFormat={optFormat} fn={pick} />
    </>;
}
