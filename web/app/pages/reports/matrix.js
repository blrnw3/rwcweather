import { Box, Flex, Grid, Heading, Spinner, Text, useRadioGroup } from "@chakra-ui/react";
import { Fragment, useContext, useState } from 'react';
import useSWR from 'swr';
import { fetcher, fmatAggTypeOpt, fmatObsOpt, OBS } from '../../components/conf';
import { daysInMonth } from "../../components/dateUtil";
import { Page, UnitCtx } from "../../components/Page";
import RadioCard from "../../components/RadioCard";
import { convFunction, formatObs, scaleForObsType } from '../../format';

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const months = Array.from(Array(12).keys());
let loading = true;

function useSummary(obs, agg, year) {
    const { data, error, isValidating } = useSWR("/api/var/all_periods/" + obs + "/" + agg + "?year=" + year, fetcher, { refreshInterval: 300000 })
    loading = true;
    if (error || !data) {
        //   console.log(error);
        return error ? {} : {};
    }
    loading = isValidating;
    let res = data["result"];
    res["server"] = data["server"];
    return res;
}

function getStyleForObsValue(val, obsType, unit) {
    if (val == null) {
        return "gray.300"
    }
    val = convFunction(unit, obsType)(val);
    const scale = scaleForObsType(unit, obsType);
    let i = 0;
    while (i < scale.length) {
        if (val < scale[i]) {
            break;
        }
        i++;
    }
    let bg = "brand." + ((i == 0) ? 50 : i * 100).toString();
    let col = (i > 5) ? "white" : "black";
    return { bg, col }
}

function RadioButtonGroup(props) {
    let { getRootProps, getRadioProps } = useRadioGroup({
        name: props.name,
        defaultValue: props.options[0],
        onChange: props.fn,
    })
    const group = getRootProps()
    return <Flex wrap="wrap" py="1" id={props.name} {...group}>
        {props.options.map((value) => {
            const radio = getRadioProps({ value });
            return (
                <RadioCard key={value} {...radio}>
                    {props.optFormat(value)}
                </RadioCard>
            )
        })}
    </Flex>
}

function DailyMatrix(props) {
    const obs = props.obs;
    const obsObj = OBS.get(obs);
    const agg = props.aggType;
    const summary = useSummary(obs, agg, props.year);
    const res = summary?.daily || [];
    let serverDateParts = summary?.["server"]?.["date"] || [2000, 1, 1];
    const year = serverDateParts[0];
    let today = new Date(serverDateParts[0], serverDateParts[1] - 1, serverDateParts[2]);
    let unit = useContext(UnitCtx);

    // Convert input to matrix structure (map of month->array<day>)
    let data = new Map();
    for (let r of res) {
        let mon = months[r["d"][1] - 1];
        if (!data.has(mon)) {
            data.set(mon, Array(31));
        }
        data.get(mon)[r["d"][2]] = r["val"];
    }

    return <Grid id="obs-matrix-days"
        templateColumns="0.8fr repeat(12, 1fr)"
        templateRows="30px auto"
        overflow="auto"
        marginTop="4"
        columnGap={{base: 1, md: 2, lg: 3, xl: 5}}
    >
        <Flex justifyContent="center" fontSize="lg">{loading ? <Spinner size="sm" /> : obsObj.icon}</Flex>
        {months.map((m) => {
            return <Box key={m} fontWeight="bold" textAlign="center">{monthNames[m]}</Box>
        })}
        {Array.from(Array(31).keys()).map((i) => {
            let d = i + 1;
            return <Fragment key={"dm-frag-" + d.toString()}>
                <Box display="contents" sx={{ ":hover > div": { backgroundColor: "gray.400" } }}>
                    <Box minW="32px" className="day" textAlign="center" key={d.toString()}>{d}</Box>
                    {months.map((m) => {
                        let thisDate = new Date(year, m, d);
                        let v = "";
                        let col = "black";
                        let bg = "gray.200";
                        let hover = {}
                        if (d > daysInMonth(year, m + 1)) {
                            // Invalid day
                            bg = ""
                        }
                        else if (thisDate > today) {
                            // Day in the future: use defaults
                        }
                        else if (!data.has(m)) {
                            // v = thisDate.toString();
                        }
                        else if (data.get(m)[d] == null) {
                            // No data for day
                            v = "-"
                            bg = "gray.300";
                            hover = { border: "1px solid #999" };
                        }
                        else {
                            v = formatObs(unit, data.get(m)[d], obsObj.fmat, false, false);
                            ({ bg, col } = getStyleForObsValue(data.get(m)[d], obsObj.fmat, unit));
                            hover = { border: "1px solid " + col };
                        }
                        let bgComps = bg.split(".");
                        bg = "var(--chakra-colors-" + bgComps[0] + "-" + bgComps[1] + ") !important";
                        return <Box key={m.toString() + "-" + d.toString()} className="cell"
                            textAlign="center" backgroundColor={bg} color={col}
                            border="1px solid transparent"
                            _hover={hover} px={1}
                        >
                            {v}</Box>
                    })}
                </Box>
            </Fragment>
        })}
    </Grid>
}

function MonthlyMatrix(props) {
    const obs = props.obs;
    const obsObj = OBS.get(obs);
    const agg = props.aggType;
    const summary = useSummary(obs, agg, props.year);
    const res = summary?.monthly || [];
    let unit = useContext(UnitCtx);

    const summaries = new Map();
    summaries.set("min_val", "Min");
    summaries.set("max_val", "Max");
    summaries.set(obsObj.summary, (obsObj.summary == "avg") ? "Avg" : "Total");

    // Convert input to matrix structure (map of month->summary_obj)
    let data = new Map();
    for (let r of res) {
        let mon = months[r["m"][1] - 1];
        data.set(mon, r["summary"]);
    }

    return <Grid id="obs-matrix-months" key="obs-matrix-months"
        templateColumns="0.8fr repeat(12, 1fr)"
        templateRows="30px auto"
        overflow="auto"
        marginTop={3}
        rowGap="2"
        columnGap={{base: 1, md: 2, lg: 3, xl: 5}}
    >
        <Flex justifyContent="center" fontSize="lg">{obsObj.icon}</Flex>
        {months.map((m) => {
            return <Box key={m} fontWeight="bold" textAlign="center">{monthNames[m]}</Box>
        })}
        {Array.from(summaries, ([k, val]) => {
            return <Fragment key={"mm-frag-" + k}>
                <Box py="2" minW="32px" className="summary" key={k} textAlign="center">{val}</Box>
                {months.map((m) => {
                    let v = "";
                    let col = "black";
                    let bg = "gray.200";
                    let hover = {}
                    if (data.has(m)) {
                        v = formatObs(unit, data.get(m)[k], obsObj.fmat, false, false);
                        ({ bg, col } = getStyleForObsValue(data.get(m)[k], obsObj.fmat, unit));
                        hover = { border: "1px solid " + col };
                    }
                    return <Box key={m + "-" + k} className="cell"
                        textAlign="center" backgroundColor={bg} color={col}
                        border="1px solid transparent"
                        _hover={hover}
                        py="2" px="1"
                    >
                        {v}</Box>
                })}
            </Fragment>
        })}
    </Grid>

}

export default function Obs() {
    const [obs, setObs] = useState("temp");
    const [aggType, setAggType] = useState("max");
    const [aggOpts, setAggOpts] = useState(["max", "min", "avg"]);
    const year = new Date().getFullYear();

    const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt"];

    const handleObsChange = (x) => {
        setObs(x);
        let aggOptsOk = (x === "rain") ? ["total"] : ["max", "min", "avg"];
        setAggOpts(aggOptsOk);
        if (x === "rain") {
            setAggType("total");
        } else if (aggType === "total") {
            setAggType("max");
        }
    }

    return <Page name="reports" title="Reports | matrix">
        <Heading as="h1" size="1">
            Reports: Annual matrix
        </Heading>
        <Heading as="h2" size="2">
            Daily {fmatAggTypeOpt(aggType)} {OBS.get(obs).name} this year
        </Heading>

        <RadioButtonGroup name="obs" options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
        <RadioButtonGroup name="agg" options={aggOpts} optFormat={fmatAggTypeOpt} fn={setAggType} />
        
        <DailyMatrix obs={obs} aggType={aggType} year={year} />
        <MonthlyMatrix obs={obs} aggType={aggType} year={year} />

        <Text mt="3">
            Description: daily {fmatAggTypeOpt(aggType)} {OBS.get(obs).name} data for every day this year, along with
            monthly aggregations - monthly maximum, minimum and averages for each month.
        </Text>

    </Page>

}
