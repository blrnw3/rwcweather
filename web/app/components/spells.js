import { Text } from "@chakra-ui/react";
import { useContext, useEffect } from "react";
import { UnitCtx } from "./Page";
import { fmatForObs } from "./conf";
import { formatObs } from "../format";
import {
    cToF,
    DAILY_AGGREGATION_NAMES,
    inHgToMb,
    kphToMph,
    mmToIn,
    nearestThreshold,
    RadioButtonGroup,
} from "./report";

// Spells: longest runs of consecutive days above (>=) or below (<) a threshold,
// ranked or gridded server-side (see rwcwx/calc/spells.py). Thresholds are in
// inches, °F or hours, mirroring SPELL_VARS there.

export const SPELL_CONF = {
    rain: { total: ["0.01", "0.1", "0.25", "0.5", "1"] },
    wet: { total: ["1", "3", "6", "12"] },
    wetrate: { avg: ["0.02", "0.05", "0.1", "0.2"] },
    rain60: { max: ["0.05", "0.1", "0.25", "0.5"] },
    rain10: { max: ["0.02", "0.05", "0.1", "0.2"] },
    temp: {
        max: ["40", "50", "60", "70", "80", "90", "100"],
        min: ["32", "40", "45", "50", "55", "60"],
        avg: ["40", "50", "60", "70", "80"],
    },
    sun: { total: ["0.1", "1", "4", "8", "10", "12"] },
    sunpct: { avg: ["10", "25", "50", "75", "90"] },
    fog: { total: ["0.5", "1", "2", "3", "4"] },
    fogday: { total: ["1"] },
    humi: {
        max: ["50", "60", "70", "80", "90", "95"],
        min: ["20", "30", "40", "50", "60", "70"],
        avg: ["30", "40", "50", "60", "70", "80", "90"],
    },
    dewpt: {
        max: ["32", "40", "50", "55", "60", "65"],
        min: ["25", "32", "40", "45", "50", "55"],
        avg: ["32", "40", "45", "50", "55", "60"],
    },
    aqi: {
        max: ["25", "50", "100", "150", "200"],
        min: ["10", "25", "50", "100"],
        avg: ["25", "50", "100", "150"],
    },
    wind: {
        max: ["5", "10", "15", "20", "25"],
        avg: ["2", "4", "6", "8", "10"],
        min: ["1", "2", "5"],
    },
    gust: {
        max: ["10", "15", "20", "25", "30", "40"],
        avg: ["4", "6", "8", "10", "15"],
        min: ["1", "2", "5"],
    },
    pres: {
        max: ["1005", "1010", "1015", "1020", "1025"],
        min: ["1005", "1010", "1015", "1020", "1025"],
        avg: ["1005", "1010", "1015", "1020", "1025"],
    },
};
// Metric users (uk & eu) get round Celsius and mm thresholds, stored as their °F / inch equivalents
// to match SPELL_VARS in rwcwx/calc/spells.py.
const SPELL_CONF_METRIC = {
    rain: { total: ["0.01", ...[1, 2.5, 5, 10, 25].map(mmToIn)] },
    wetrate: { avg: [0.5, 1, 2, 5].map(mmToIn) },
    rain60: { max: [1, 2, 5, 10].map(mmToIn) },
    rain10: { max: [0.5, 1, 2, 5].map(mmToIn) },
    temp: {
        max: [10, 15, 20, 25, 30, 35, 40].map(cToF),
        min: [0, 5, 10, 15].map(cToF),
        avg: [5, 10, 15, 20, 25].map(cToF),
    },
    dewpt: {
        max: [0, 5, 10, 15, 20].map(cToF),
        min: [-5, 0, 5, 10, 15].map(cToF),
        avg: [0, 5, 10, 15, 20].map(cToF),
    },
};
const SPELL_CONF_EU = {
    wind: {
        max: [10, 15, 20, 30, 40].map(kphToMph),
        avg: [5, 10, 15, 20].map(kphToMph),
        min: [2, 5, 10].map(kphToMph),
    },
    gust: {
        max: [15, 25, 30, 40, 50, 60].map(kphToMph),
        avg: [5, 10, 15, 20].map(kphToMph),
        min: [2, 5, 10].map(kphToMph),
    },
};
const SPELL_CONF_US = {
    pres: {
        max: [29.7, 29.8, 29.9, 30.0, 30.1, 30.2].map(inHgToMb),
        min: [29.7, 29.8, 29.9, 30.0, 30.1, 30.2].map(inHgToMb),
        avg: [29.7, 29.8, 29.9, 30.0, 30.1, 30.2].map(inHgToMb),
    },
};
export const SPELL_OBS = Object.keys(SPELL_CONF);

// Opening defaults: wet days for rain, warm days for temperatures, sunny days for sunshine.
const SPELL_DEFAULTS = {
    rain: "0.01", wet: "1", wetrate: "0.05", rain60: "0.1", rain10: "0.05",
    max: "80", min: "50", avg: "60",
    sun: "10", sunpct: "75", fog: "1", fogday: "1",
    humi: "70", dewpt: "50", aqi: "50", wind: "10", gust: "20", pres: "1015",
};
export const DEFAULT_SPELL_DIR_NAMES = { above: "Above (≥)", below: "Below (<)" };
export const SPELL_DIR_NAMES = {
    rain: { above: "Wet (≥)", below: "Dry (<)" },
    wet: { above: "Wet (≥)", below: "Mostly dry (<)" },
    temp: { above: "Above (≥)", below: "Below (<)" },
    sun: { above: "Sunny (≥)", below: "Dull (<)" },
    sunpct: { above: "Sunny (≥)", below: "Dull (<)" },
    fog: { above: "Foggy (≥)", below: "Clearer (<)" },
    fogday: { above: "Fog days", below: "Fog-free days" },
};
const DEFAULT_SPELL_TITLE_WORDS = { above: "high", below: "low" };
export const SPELL_TITLE_WORDS = {
    rain: { above: "wet", below: "dry" },
    wet: { above: "wet", below: "mostly dry" },
    temp: { above: "warm", below: "cold" },
    sun: { above: "sunny", below: "dull" },
    sunpct: { above: "sunny", below: "dull" },
    fog: { above: "foggy", below: "fog-light" },
    fogday: { above: "foggy", below: "fog-free" },
    humi: { above: "humid", below: "dry" },
    wind: { above: "windy", below: "calm" },
    gust: { above: "gusty", below: "calm" },
    aqi: { above: "polluted", below: "clean" },
};
export const SPELL_STATUS = { today: ", so far", pending: ", may continue today", yesterday: ", to yesterday" };

export function spellDirNames(obs) {
    return SPELL_DIR_NAMES[obs] || DEFAULT_SPELL_DIR_NAMES;
}

export function spellTitleWord(obs, dir) {
    return (SPELL_TITLE_WORDS[obs] || DEFAULT_SPELL_TITLE_WORDS)[dir];
}

// Options shown for the unit preference ("uk" / "eu" = metric temperatures & rainfall; "eu" = kph wind).
export function spellThresholds(obs, stat, unit = "us") {
    if (unit === "eu" && SPELL_CONF_EU[obs]?.[stat]) {
        return SPELL_CONF_EU[obs][stat];
    }
    if (unit !== "us" && SPELL_CONF_METRIC[obs]?.[stat]) {
        return SPELL_CONF_METRIC[obs][stat];
    }
    if (unit === "us" && SPELL_CONF_US[obs]?.[stat]) {
        return SPELL_CONF_US[obs][stat];
    }
    return SPELL_CONF[obs]?.[stat] || [];
}

// Every value the URL / API accepts: all unit systems' options.
// 0.2 mm is the metric label for the 0.01 in dry threshold. 2 mm is no longer
// shown for rain totals, but is accepted so older links can map to 2.5 mm.
export function spellThresholdsAny(obs, stat) {
    return [...new Set([
        ...spellThresholds(obs, stat, "us"),
        ...spellThresholds(obs, stat, "uk"),
        ...spellThresholds(obs, stat, "eu"),
        ...(obs === "rain" ? [mmToIn(0.2), mmToIn(2)] : []),
    ])];
}

export function spellDefaultThreshold(obs, stat) {
    const list = spellThresholds(obs, stat);
    const def = SPELL_DEFAULTS[obs === "temp" ? stat : obs];
    return list.includes(def) ? def : list[0];
}

export function spellDailyStats(obs) {
    return Object.keys(SPELL_CONF[obs] || {});
}

export function hasSpellOptions(obs, stat) {
    return spellThresholds(obs, stat).length > 0;
}

// Thresholds are entered in °F / inches / hours; temperatures are stored (and formatted from) °C.
export function formatThreshold(unit, obs, value, stat) {
    if (obs === "wet" || obs === "sun" || obs === "fog") {
        return value + " h";
    }
    if (obs === "fogday") {
        return "fog seen";
    }
    const num = Number(value);
    if (obs === "rain" && (num === 0.01 || num === 0.0079) && unit !== "us") {
        return "0.2 mm";
    }
    if (obs === "temp" || obs === "dewpt") {
        // Whole degrees in the viewer's unit: 86 -> "30 °C" (metric) or "86 °F".
        return unit !== "us" ? Math.round((num - 32) * 5 / 9 * 10) / 10 + " °C" : num + " °F";
    }
    const fmat = fmatForObs(obs, stat);
    const raw = formatObs(unit, num, fmat);
    return unit === "us" && (fmat === "rain" || fmat === "wetrate" || fmat === "pres")
        ? raw
        : raw.replace(/\.0+(?=\s|$)/, "");
}

export function SpellThresholdSelector({ obs, dailyAggregation, value, fn }) {
    const unit = useContext(UnitCtx);
    const options = spellThresholds(obs, dailyAggregation, unit);
    const nearest = nearestThreshold(value, options);
    // A °F value in a metric view (or vice versa), e.g. from a shared link or after switching units:
    // move to the nearest option for this unit so a button is always selected.
    useEffect(() => {
        if (nearest !== value) {
            fn(nearest);
        }
    }, [nearest, value]);  // eslint-disable-line react-hooks/exhaustive-deps
    return <>
        <Text mt="1" fontWeight="bold">Threshold:</Text>
        <RadioButtonGroup name="level" value={value} options={options}
            optFormat={(v) => formatThreshold(unit, obs, v, dailyAggregation)} fn={fn} />
    </>;
}

export function SpellKindSelector({ obs, dir, fn }) {
    const names = spellDirNames(obs);
    return <>
        <Text mt="1" fontWeight="bold">Spell:</Text>
        <RadioButtonGroup name="dir" value={dir} options={["above", "below"]}
            optFormat={(value) => names[value]} fn={fn} />
    </>;
}

export function formatSpellLength(value, { average = false } = {}) {
    if (value == null || Number.isNaN(value)) {
        return "-";
    }
    if (average) {
        return Number(value).toFixed(1);
    }
    return Number.isInteger(value) ? value.toString() : Number(value).toFixed(1);
}

export function spellSummaryLabel(obs, dailyAggregation, dir, threshold, unit) {
    const word = spellTitleWord(obs, dir);
    const cmp = dir === "above" ? "≥" : "<";
    const agg = DAILY_AGGREGATION_NAMES[dailyAggregation] || "Daily";
    return "Longest " + word + " spells (" + agg + " " + cmp + " "
        + formatThreshold(unit, obs, threshold, dailyAggregation) + ")";
}
