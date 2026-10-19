import { Box, Flex, Heading, Spinner, Text, useRadioGroup } from "@chakra-ui/react";
import { useContext, useEffect, useState } from "react";
import useSWR from "swr";
import { fetcher } from "../../components/conf";
import { DayProfileChart } from "../../components/dayProfileChart";
import { Page, UnitCtx } from "../../components/Page";
import RadioCard from "../../components/RadioCard";
import { inList, useUrlState } from "../../components/urlState";
import { convFunction, unitAndPrecisionForObsType } from "../../format";

// Daily profile: the average of each variable at every time of day (5-minute bins, Pacific time),
// for all time, one year, one month of the year across all years, or one year+month.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December"];
const FIRST_YEAR = 2021;   // first full year (data from 21 Dec 2020)
const LAST_YEAR = new Date().getFullYear();
const YEARS = ["all", ...Array.from(Array(LAST_YEAR - 2020 + 1).keys()).map((i) => String(LAST_YEAR - i))];
const MONTH_OPTS = ["all", ...MONTHS.map((m) => m.toLowerCase())];

// var -> label, how to format (obs type for unit conversion, or a fixed % scale), chart colour, note
const VARS = new Map([
    ["temp", { name: "Temperature", fmat: "temp", color: "#ff7733" }],
    ["dewpt", { name: "Dew point", fmat: "temp", color: "#22aa88" }],
    ["humi", { name: "Humidity", fmat: "humi", color: "#2b8a3e" }],
    ["pres", { name: "Pressure", fmat: "pres", color: "#6a4c93" }],
    ["wind", { name: "Wind speed", fmat: "wind", color: "#555555", precision: 1 }],
    ["gust", { name: "Gust speed", fmat: "gust", color: "#993333", precision: 1 }],
    ["rain", { name: "Rain rate", fmat: "wetrate", color: "#2299dd", area: true, precision: { base: 2, us: 4 },
        note: "Average rain per hour at each time of day, counting dry days (gauge tips; logger catch-up jumps left out)." }],
    ["wet", { name: "Wet (% of time)", pct: true, precision: 1, color: "#1c7ed6", area: true,
        note: "Share of observed minutes that were wet (raining, from rain-gauge tips) at each time of day." }],
    ["sun", { name: "Sunshine (% of time)", pct: true, precision: 0, color: "#e6a700", area: true, yMax: 100,
        note: "Share of webcam-classified daytime that was sunny. Most history is classified in 30-minute snapshots, " +
            "so the curve steps every 30 minutes; nights are not classified." }],
    ["fog", { name: "Fog (% of time)", pct: true, precision: 0, color: "#868e96", area: true,
        note: "Share of webcam-judged time with fog at the station. Fog is only judged on morning frames (about 6am–1pm), " +
            "in 30-minute snapshots." }],
    ["pm2", { name: "PM2.5", fixedUnit: "µg/m³", precision: 1, color: "#8c6d1f" }],
]);
const VAR_KEYS = Array.from(VARS.keys());

const URL_STATE = {
    v: { param: "var", def: () => "temp", valid: inList(VAR_KEYS) },
    year: { def: () => "all", valid: inList(YEARS) },
    month: { def: () => "all", valid: inList(MONTH_OPTS) },
};

function Group({ name, value, options, format, onChange }) {
    const { getRootProps, getRadioProps } = useRadioGroup({ name, value, onChange });
    return <Flex wrap="wrap" py="1" id={name} {...getRootProps()}>
        {options.map((o) => <RadioCard key={o} {...getRadioProps({ value: o })}>{format(o)}</RadioCard>)}
    </Flex>;
}

function periodLabel(year, month) {
    const m = month === "all" ? null : MONTH_LONG[MONTH_OPTS.indexOf(month) - 1];
    if (year === "all") return m ? `every ${m}` : "all time";
    return m ? `${m} ${year}` : year;
}

function scaleFor(unit, cfg) {
    if (cfg.pct) return { conv: (x) => x, unitSymbol: "%", precision: cfg.precision };
    if (cfg.fixedUnit) return { conv: (x) => x, unitSymbol: cfg.fixedUnit, precision: cfg.precision };
    const { unitSymbol, precision } = unitAndPrecisionForObsType(unit, cfg.fmat);
    const p = cfg.precision == null ? precision : typeof cfg.precision === "object"
        ? (cfg.precision[unit] ?? cfg.precision.base) : cfg.precision;
    return { conv: convFunction(unit, cfg.fmat), unitSymbol, precision: p };
}

export default function DayProfile() {
    const [{ v, year, month }, update] = useUrlState(URL_STATE);
    const unit = useContext(UnitCtx);
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    const cfg = VARS.get(v);
    const params = new URLSearchParams();
    if (year !== "all") params.set("year", year);
    if (month !== "all") params.set("month", String(MONTH_OPTS.indexOf(month)));
    const qs = params.toString();
    const { data, error } = useSWR(`/api/var/profile/${v}/${qs ? "?" + qs : ""}`, fetcher, { revalidateOnFocus: false });
    const res = data?.result;
    const sc = scaleFor(unit, cfg);
    const period = periodLabel(year, month);
    const nUnit = cfg.pct && v !== "wet" ? "classified minutes" : "minutes of data";
    const points = res?.avg ? res.avg.map((y, i) => y == null ? { x: i * res.bin_min, y: null }
        : { x: i * res.bin_min, y: Number(sc.conv(y).toFixed(sc.precision + 1)), n: res.n[i], unitN: nUnit }) : null;
    const hasData = points && points.some((p) => p.y != null);

    return <Page name="reports" sub="daily profile" title="Reports | daily profile">
        <Heading as="h1" size="1">Reports: Daily profile</Heading>
        <Heading as="h2" size="2">Average {cfg.name.toLowerCase()} through the day, {period}</Heading>
        <Group name="var" value={v} options={VAR_KEYS} format={(k) => VARS.get(k).name.replace(" (% of time)", "")}
            onChange={(x) => update({ v: x })} />
        <Group name="year" value={year} options={YEARS} format={(y) => y === "all" ? "All years" : y}
            onChange={(x) => update({ year: x })} />
        <Group name="month" value={month} options={MONTH_OPTS} format={(m) => m === "all" ? "All months" : MONTHS[MONTH_OPTS.indexOf(m) - 1]}
            onChange={(x) => update({ month: x })} />
        <Box mt="3" minH={{ base: "340px", md: "440px" }} className="day-profile-chart">
            {!mounted || (!data && !error) ? <Spinner m="6" /> : error || !hasData
                ? <Text m="6">No data for {period}.</Text>
                : <DayProfileChart points={points} binMin={res.bin_min} name={cfg.name} unitSymbol={sc.unitSymbol}
                    precision={sc.precision} color={cfg.color} area={cfg.area} yMin={cfg.pct || v === "rain" ? 0 : undefined}
                    yMax={cfg.yMax} title={`${cfg.name}, ${period}`} />}
        </Box>
        {res && <Text fontSize="sm" color="gray.600">
            {res.days.toLocaleString()} days ({res.start} to {res.end}), {res.bin_min}-minute bins, Pacific time.
            {year === "all" && month === "all" && ` Records start 21 Dec 2020; ${FIRST_YEAR} is the first full year.`}
        </Text>}
        {cfg.note && <Text mt="1" fontSize="sm" color="gray.600">{cfg.note}</Text>}
        <Text mt="3">
            Description: the average {cfg.name.toLowerCase()} at each time of day, from every minute of data in the
            chosen period. Pick a year, a month (that month in every year), or both. Drag across the chart to zoom in.
        </Text>
    </Page>;
}
