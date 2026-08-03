import { Box, Flex, Text, useRadioGroup } from "@chakra-ui/react";
import { useContext } from "react";
import { convFunction, formatObs, scaleForObsType } from "../format";
import { OBS } from "./conf";
import { UnitCtx } from "./Page";
import RadioCard from "./RadioCard";

export const REPORT_YEAR_START = 2021;

export const REPORT_OBS_OPTIONS = [
    "temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt", "gust",
];

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
    return obs === "rain" ? ["total"] : ["min", "max", "avg"];
}

export function summaryOptions(obs) {
    return ["min", "max", OBS.get(obs).summary, "count"];
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

export function styleForReportValue(value, obsType, unit, summary, annual = false) {
    if (summary === "count") {
        const scale = annual
            ? [1, 50, 100, 150, 200, 250, 300, 365]
            : [1, 5, 10, 15, 20, 25, 28, 31];
        return styleForScaleValue(value, scale);
    }
    const convertedValue = value == null ? null : convFunction(unit, obsType)(value);
    return styleForScaleValue(convertedValue, scaleForObsType(unit, obsType));
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
