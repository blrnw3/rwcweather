import {
    Box,
    Button,
    Flex,
    Heading,
    Input,
    Link as ChakraLink,
    SimpleGrid,
    Spinner,
    Table,
    Tbody,
    Td,
    Text,
    Th,
    Thead,
    Tr,
} from "@chakra-ui/react";
import { useContext, useEffect, useState } from "react";
import useSWR from "swr";
import { DailyChart } from "../../components/chart";
import { baseObs, fetcher, fmatForObs, fmatObsOpt, OBS } from "../../components/conf";
import { Page, UnitCtx } from "../../components/Page";
import { inList, useUrlState } from "../../components/urlState";
import { DerivedVarNote, MINUTE_OBS_STATES, RadioButtonGroup, REPORT_OBS_OPTIONS, styleForReportValue, SunViewToggle } from "../../components/report";
import { SunLegend, SunRibbon, useSunDay } from "../../components/sun";
import { useWetDay, WetLegend, WetRibbon } from "../../components/wet";
import { formatObs, timeOf } from "../../format";
import { ClimateAnom, ClimateNormalsLink, ClimateNote, dailyNormal, hasClimate } from "../../components/climate";

const STATION_TIME_ZONE = "America/Los_Angeles";
const SUMMARY_ROWS = [
    ["temperature", "temp"],
    ["dew_point", "dewpt"],
    ["humidity", "humi"],
    ["pressure", "pres"],
    ["wind_speed", "wind"],
    ["gust_speed", "gust"],
    ["wind_direction", "wdir"],
    ["rain", "rain"],
    ["aqi", "aqi"],
];

function stationToday() {
    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: STATION_TIME_ZONE,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
    return values.year + "-" + values.month + "-" + values.day;
}

function stationNowHm() {
    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: STATION_TIME_ZONE,
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
    }).formatToParts(new Date());
    const h = Number(parts.find(({ type }) => type === "hour")?.value || 0);
    const m = Number(parts.find(({ type }) => type === "minute")?.value || 0);
    return [h, m];
}

function shiftDate(date, amount) {
    const [year, month, day] = date.split("-").map(Number);
    const shifted = new Date(Date.UTC(year, month - 1, day + amount));
    return shifted.toISOString().slice(0, 10);
}

function prettyDate(date) {
    if (!date) {
        return "";
    }
    return new Intl.DateTimeFormat("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
    }).format(new Date(date + "T12:00:00Z"));
}

function stationTime(timestamp) {
    if (timestamp == null) {
        return "-";
    }
    return new Intl.DateTimeFormat("en-US", {
        hour: "numeric",
        minute: "2-digit",
        timeZone: STATION_TIME_ZONE,
    }).format(new Date(timestamp));
}

// Daily climate comparison (as on nw3weather's daily report): temperature
// low / high / mean, mean wind speed, and sunshine total against that day's normal.
// Daily rain totals are not compared, since a single day's rain vs normal is meaningless.
function dayNormal(obs, summary, date) {
    const stat = summary === "min" ? "min" : summary === "max" ? "max" : summary === "total" ? "total" : "avg";
    if (!date || obs === "rain" || (obs !== "temp" && obs !== "sun" && stat !== "avg") || !hasClimate(obs, stat)) {
        return null;
    }
    const [year, month, day] = date.split("-").map(Number);
    return { stat, normal: dailyNormal(obs, stat, year, month, day) };
}

function SummaryCell({ value, at, obs, summary, unit, date }) {
    const fmat = fmatForObs(obs, summary);
    const { bg, col } = styleForReportValue(value, fmat, unit, summary);
    const climate = dayNormal(obs, summary, date);
    return <Td isNumeric backgroundColor={bg} color={col}>
        <Text fontWeight="bold">{formatObs(unit, value, fmat)}</Text>
        {climate && <ClimateAnom value={value} normal={climate.normal} obs={obs} stat={climate.stat} unit={unit} />}
        {at != null && <Text fontSize="xs">at {stationTime(at)}</Text>}
    </Td>;
}

// Derived daily values (rwcwx/calc/derived_daily.py): ranges are the day's max - min of the summary above;
// ET0 comes from the API (past days only).
const RANGE_ROWS = [["temperature", "temprange"], ["dew_point", "dewptrange"], ["humidity", "humirange"], ["pressure", "presrange"]];

function DerivedSummary({ summary, et0 }) {
    const unit = useContext(UnitCtx);
    const cell = (obs, v) => {
        const { bg, col } = styleForReportValue(v, OBS.get(obs).fmat, unit, OBS.get(obs).summary);
        return <Td isNumeric bg={bg} color={col}>{formatObs(unit, v, OBS.get(obs).fmat)}</Td>;
    };
    return <Box mt="4" overflowX="auto">
        <Table id="daily-derived-table" variant="simple" size="md" maxWidth="680px">
            <Thead><Tr><Th>Derived</Th><Th isNumeric>Value</Th><Th>Note</Th></Tr></Thead>
            <Tbody>
                {RANGE_ROWS.map(([key, obs]) => {
                    const st = summary?.[key] || {};
                    const v = st.max_val != null && st.min_val != null ? st.max_val - st.min_val : null;
                    return <Tr key={obs}><Td fontWeight="bold">{OBS.get(obs).name}</Td>{cell(obs, v)}<Td fontSize="sm">max − min</Td></Tr>;
                })}
                <Tr key="et0"><Td fontWeight="bold">ET0 (reference evapotranspiration)</Td>{cell("et0", et0?.val ?? null)}
                    <Td fontSize="sm">{et0?.method === "pm" ? "FAO-56 Penman-Monteith" : et0?.method === "hs" ? "Hargreaves-Samani (no usable sunshine)" : "not for today"}</Td></Tr>
            </Tbody>
        </Table>
        <DerivedVarNote obs="et0" mt="2" />
    </Box>;
}

function DailySummary({ summary, date }) {
    const unit = useContext(UnitCtx);

    return <Box mt="5" overflowX="auto">
        <Heading as="h3" size="3">Summary statistics</Heading>
        <Table id="daily-summary-table" variant="simple" size="md" minWidth="680px">
            <Thead>
                <Tr>
                    <Th>Variable</Th>
                    <Th isNumeric>Minimum</Th>
                    <Th isNumeric>Maximum</Th>
                    <Th isNumeric>Mean / total</Th>
                    <Th isNumeric>Readings</Th>
                </Tr>
            </Thead>
            <Tbody>
                {SUMMARY_ROWS.map(([summaryKey, obs]) => {
                    const stats = summary?.[summaryKey] || {};
                    const middleKey = obs === "rain" ? "total" : "avg";
                    return <Tr key={summaryKey}>
                        <Td fontWeight="bold">{OBS.get(obs).name}</Td>
                        <SummaryCell value={stats.min_val} at={stats.min_at} obs={obs} summary="min" unit={unit} date={date} />
                        <SummaryCell value={stats.max_val} at={stats.max_at} obs={obs} summary="max" unit={unit} date={date} />
                        <SummaryCell value={stats[middleKey]} obs={obs} summary={middleKey} unit={unit} date={date} />
                        <Td isNumeric>{stats.count ?? 0}</Td>
                    </Tr>;
                })}
            </Tbody>
        </Table>
        <ClimateNote currentPeriodNote={false} />
    </Box>;
}

function formatSlotTime(hour, minute = 0) {
    const mm = String(minute).padStart(2, "0");
    const h12 = hour % 12 || 12;
    return h12 + ":" + mm + " " + (hour < 12 ? "AM" : "PM");
}

function stationDateTimeParts(timestamp) {
    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: STATION_TIME_ZONE,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
    }).formatToParts(new Date(timestamp));
    return Object.fromEntries(parts.map(({ type, value }) => [type, value]));
}

function stationOffsetMs(timestamp) {
    const parts = stationDateTimeParts(timestamp);
    const wallTimeAsUtc = Date.UTC(
        Number(parts.year), Number(parts.month) - 1, Number(parts.day),
        Number(parts.hour), Number(parts.minute)
    );
    return wallTimeAsUtc - timestamp;
}

function slotEpochMs(date, hour, minute = 0) {
    const [year, month, day] = date.split("-").map(Number);
    const desiredWallTime = Date.UTC(year, month - 1, day, hour, minute);
    const noonUtc = Date.UTC(year, month - 1, day, 12);
    let archiveTime = desiredWallTime - stationOffsetMs(noonUtc);
    archiveTime = desiredWallTime - stationOffsetMs(archiveTime);

    const stationParts = stationDateTimeParts(archiveTime);
    if (Number(stationParts.year) !== year
        || Number(stationParts.month) !== month
        || Number(stationParts.day) !== day
        || Number(stationParts.hour) !== hour
        || Number(stationParts.minute) !== minute) {
        return null;
    }
    return archiveTime;
}

function webcamArchiveStamp(date, hour, minute = 0) {
    const archiveTime = slotEpochMs(date, hour, minute);
    if (archiveTime == null) {
        return null;
    }
    const utc = new Date(archiveTime);
    return utc.getUTCFullYear().toString()
        + (utc.getUTCMonth() + 1).toString().padStart(2, "0")
        + utc.getUTCDate().toString().padStart(2, "0")
        + "_"
        + utc.getUTCHours().toString().padStart(2, "0")
        + utc.getUTCMinutes().toString().padStart(2, "0");
}

function WebcamImage({ date, dateLabel, hour, minute = 0 }) {
    const [missing, setMissing] = useState(false);
    const slotLabel = formatSlotTime(hour, minute);
    const archiveStamp = webcamArchiveStamp(date, hour, minute);
    const imageUrl = archiveStamp
        ? "https://rwcweather.com/cumulus/camdump/sky_lg/" + archiveStamp + ".jpg"
        : null;

    return <Box border="1px solid" borderColor="gray.300" borderRadius="md" overflow="hidden" backgroundColor="white">
        {missing || !imageUrl
            ? <Flex style={{ aspectRatio: "16 / 9" }} align="center" justify="center" backgroundColor="gray.200" color="gray.600">
                <Text>No archived image</Text>
            </Flex>
            : <ChakraLink href={imageUrl} isExternal display="block" title={"Open " + slotLabel + " image"}>
                <Box
                    as="img"
                    src={imageUrl}
                    alt={"Redwood City webcam at " + slotLabel + " on " + dateLabel}
                    loading="lazy"
                    width="100%"
                    style={{ aspectRatio: "16 / 9" }}
                    objectFit="cover"
                    onError={() => setMissing(true)}
                />
            </ChakraLink>}
        <Text px="3" py="2" fontWeight="bold">{slotLabel}</Text>
    </Box>;
}

const CAM_INTERVALS = ["60", "30", "15"];
const CAM_SPANS = ["daytime", "all"];
const CAM_SPAN_NAMES = { daytime: "Daytime (incl. twilight)", all: "All day" };

// Civil twilight bounds (sun 6° below horizon) in UTC ms for `date` at 37.469, -122.265.
function twilightBoundsMs(date, sunDay) {
    if (sunDay?.dawn && sunDay?.dusk) {
        return [sunDay.dawn, sunDay.dusk];
    }
    if (sunDay?.sunrise && sunDay?.sunset) {
        return [sunDay.sunrise - 30 * 60000, sunDay.sunset + 30 * 60000];
    }
    return [slotEpochMs(date, 5, 30), slotEpochMs(date, 21, 0)];
}

function WebcamGallery({ date, dateLabel, isToday, currentHm, datestamp }) {
    const [interval, setIntervalMin] = useState("60");
    const [span, setSpan] = useState("daytime");
    const { day: sunDay } = useSunDay(datestamp);

    const step = Number(interval);
    const [curH, curM] = currentHm;
    const maxMins = isToday ? curH * 60 + curM : 24 * 60 - 1;
    const [dawnMs, duskMs] = twilightBoundsMs(date, sunDay);

    const slots = [];
    for (let m = 0; m <= maxMins; m += step) {
        const hour = Math.floor(m / 60);
        const minute = m % 60;
        if (span === "daytime" && dawnMs != null && duskMs != null) {
            const t = slotEpochMs(date, hour, minute);
            // Include the interval containing dawn through the interval containing dusk.
            if (t != null && (t + step * 60000 <= dawnMs || t > duskMs)) {
                continue;
            }
        }
        slots.push([hour, minute]);
    }

    return <Box mt="6">
        <Heading as="h3" size="3">Webcam archive</Heading>
        <Text mb="2">Archived webcam images in Redwood City local time.</Text>
        <Flex wrap="wrap" gap="4" mb="3" align="center">
            <Box>
                <Text fontWeight="bold" fontSize="sm">Interval:</Text>
                <RadioButtonGroup
                    name="webcam-interval"
                    value={interval}
                    options={CAM_INTERVALS}
                    optFormat={(v) => v + " min"}
                    fn={setIntervalMin}
                />
            </Box>
            <Box>
                <Text fontWeight="bold" fontSize="sm">Hours:</Text>
                <RadioButtonGroup
                    name="webcam-span"
                    value={span}
                    options={CAM_SPANS}
                    optFormat={(v) => CAM_SPAN_NAMES[v]}
                    fn={setSpan}
                />
            </Box>
        </Flex>
        <SimpleGrid columns={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="3">
            {slots.map(([hour, minute]) =>
                <WebcamImage
                    key={date + "-" + hour + "-" + minute}
                    date={date}
                    dateLabel={dateLabel}
                    hour={hour}
                    minute={minute}
                />
            )}
        </SimpleGrid>
    </Box>;
}

// Webcam sunshine for the day: total and the minute ribbon. Hidden when there is no sunshine data for the day.
function DailySunshine({ datestamp }) {
    const unit = useContext(UnitCtx);
    const { day, now } = useSunDay(datestamp);
    if (!day || (!day.total && !(day.spells || []).length)) {
        return null;
    }
    const total = day.total?.hours;
    return <Box mt="6" className="daily-sunshine">
        <Heading as="h3" size="3">Sunshine</Heading>
        <Text>
            <Text as="span" fontWeight="bold">{total != null ? formatObs(unit, total, "sun") : "–"}</Text>
            {" of "}{formatObs(unit, day.daylight_h, "sun")} daylight
            {total != null && day.daylight_h ? " (" + Math.round(100 * total / day.daylight_h) + "%)" : ""}
            {day.total?.comment?.startsWith("API estimate")
                ? " · estimated from weather-model sunshine and airport cloud reports (webcam data missing)"
                : <>
                    {day.total?.comment?.includes("scaled") ? " · estimated for gaps" : ""}
                    {day.backfill ? " · estimated from 30-min snapshots" : ""}
                </>}
        </Text>
        <Box maxW="900px" my="2"><SunRibbon day={day} nowMs={now} height="22px" /></Box>
        <SunLegend />
    </Box>;
}

// Wet hours for the day (from the stored wet minutes): total, spells and the midnight-to-midnight bar.
// Hidden on dry days.
function DailyWet({ datestamp }) {
    const unit = useContext(UnitCtx);
    const { wet, now } = useWetDay(datestamp);
    if (!wet || !(wet.wet_h > 0)) {
        return null;
    }
    const elapsed = Math.min(now || wet.day_end, wet.day_end) - wet.day_start;
    const pct = elapsed > 0 ? Math.round(100 * wet.wet_h * 3600000 / elapsed) : null;
    return <Box mt="6" className="daily-wet">
        <Heading as="h3" size="3">Wet hours</Heading>
        <Text>
            <Text as="span" fontWeight="bold">{formatObs(unit, wet.wet_h, "wet")}</Text> wet
            {pct != null ? " (" + pct + "% of the day" + (now && now < wet.day_end ? " so far" : "") + ")" : ""}
            {" · "}{wet.spells} spell{wet.spells === 1 ? "" : "s"}, longest {formatObs(unit, wet.longest_h, "wet")}
            {wet.rate != null ? " · " + formatObs(unit, wet.rate, "rain") + "/h when wet" : ""}
        </Text>
        <Box maxW="900px" my="2"><WetRibbon wet={wet} nowMs={now} height="22px" /></Box>
        <WetLegend />
    </Box>;
}

// Max rain in any 10 / 60 minutes for the day, with the time it was reached. Hidden on dry days.
function DailyRainIntensity({ intensity }) {
    const unit = useContext(UnitCtx);
    if (!intensity || !(intensity.rain10?.val > 0 || intensity.rain60?.val > 0)) {
        return null;
    }
    const line = (label, v) => <Text>{label}: <Text as="span" fontWeight="bold">{formatObs(unit, v?.val, "rain")}</Text>
        {v?.at ? " ending " + timeOf(v.at) : ""}</Text>;
    return <Box mt="6" className="daily-rain-intensity">
        <Heading as="h3" size="3">Rain intensity</Heading>
        {line("Max in 10 minutes", intensity.rain10)}
        {line("Max in 60 minutes", intensity.rain60)}
    </Box>;
}

// Selections kept in the URL, e.g. /reports/day?date=2026-10-05&var=rain
const DAY_URL_STATE = {
    date: {
        def: () => "",
        valid: (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && v <= stationToday(),
    },
    obs: { param: "var", def: () => "temp", valid: inList(MINUTE_OBS_STATES) },
};

export default function DailyReport() {
    const [today, setToday] = useState("");
    const [currentHm, setCurrentHm] = useState([0, 0]);
    const [{ date, obs }, update, ready] = useUrlState(DAY_URL_STATE);

    useEffect(() => {
        setToday(stationToday());
        setCurrentHm(stationNowHm());
    }, []);

    // An empty date means "today" (the default, left out of the URL); the
    // query is only known after hydration, so wait for it before fetching.
    const selectedDate = ready && today ? (date || today) : "";
    const setSelectedDate = (value) => update({ date: value === today ? "" : value });
    const setObs = (value) => update({ obs: value });

    const datestamp = selectedDate.replace(/-/g, "");
    const url = datestamp ? "/api/web/report/day/" + datestamp : null;
    const { data: response, error, isValidating } = useSWR(url, fetcher, {
        revalidateOnFocus: false,
    });
    const report = response?.result;
    const observations = report?.observations || [];
    const dateLabel = prettyDate(selectedDate);
    const isLoading = Boolean(selectedDate && !response && !error);

    return <Page name="reports" sub="daily" title="Reports | daily">
        <Heading as="h1" size="1">Reports: Daily weather</Heading>
        <Heading as="h2" size="2">{dateLabel || "Choose a date"}</Heading>
        <ClimateNormalsLink />

        <Text fontWeight="bold">Date:</Text>
        <Flex align="center" wrap="wrap" gap="2" mb="3">
            <Button onClick={() => setSelectedDate(shiftDate(selectedDate, -1))} disabled={!selectedDate}>
                Previous day
            </Button>
            <Input
                type="date"
                value={selectedDate}
                max={today}
                onChange={(event) => setSelectedDate(event.target.value)}
                width="auto"
                backgroundColor="white"
                aria-label="Report date"
            />
            <Button
                onClick={() => setSelectedDate(shiftDate(selectedDate, 1))}
                disabled={!selectedDate || selectedDate >= today}
            >
                Next day
            </Button>
            {isValidating && <Spinner size="sm" />}
        </Flex>

        {error && <Text color="red.600">Unable to load the daily report.</Text>}
        {isLoading && <Flex py="8" align="center" gap="3"><Spinner /> Loading daily report…</Flex>}
        {report && <>
            {observations.length === 0 && <Text py="3">No observations are available for this date.</Text>}
            <DailySummary summary={report.summary} date={selectedDate} />
            <DerivedSummary summary={report.summary} et0={report.et0} />
            <DailySunshine datestamp={datestamp} />
            <DailyWet datestamp={datestamp} />
            <DailyRainIntensity intensity={report.rain_intensity} />

            <Box mt="6">
                <Heading as="h3" size="3">Daily graph</Heading>
                <Text fontWeight="bold">Variable:</Text>
                <RadioButtonGroup
                    name="daily-graph-variable"
                    value={baseObs(obs)}
                    options={REPORT_OBS_OPTIONS}
                    optFormat={fmatObsOpt}
                    fn={setObs}
                />
                {baseObs(obs) === "wind" && <SunViewToggle obs={obs} fn={setObs} summaryMode={false} />}
                <DailyChart
                    observations={observations}
                    obs={obs}
                    dateLabel={dateLabel}
                    isLoading={isLoading}
                    my="4"
                    mx={{ base: 0, md: 4, xl: 6 }}
                />
            </Box>

            <WebcamGallery
                date={selectedDate}
                dateLabel={dateLabel}
                isToday={selectedDate === today}
                currentHm={currentHm}
                datestamp={datestamp}
            />
        </>}
    </Page>;
}
