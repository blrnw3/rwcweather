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
import { fetcher, fmatObsOpt, OBS } from "../../components/conf";
import { Page, UnitCtx } from "../../components/Page";
import { RadioButtonGroup, REPORT_OBS_OPTIONS, styleForReportValue } from "../../components/report";
import { formatObs } from "../../format";

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

function stationHour() {
    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: STATION_TIME_ZONE,
        hour: "2-digit",
        hourCycle: "h23",
    }).formatToParts(new Date());
    return Number(parts.find(({ type }) => type === "hour")?.value || 0);
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

function SummaryCell({ value, at, obs, summary, unit }) {
    const obsObj = OBS.get(obs);
    const { bg, col } = styleForReportValue(value, obsObj.fmat, unit, summary);
    return <Td isNumeric backgroundColor={bg} color={col}>
        <Text fontWeight="bold">{formatObs(unit, value, obsObj.fmat)}</Text>
        {at != null && <Text fontSize="xs">at {stationTime(at)}</Text>}
    </Td>;
}

function DailySummary({ summary }) {
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
                        <SummaryCell value={stats.min_val} at={stats.min_at} obs={obs} summary="min" unit={unit} />
                        <SummaryCell value={stats.max_val} at={stats.max_at} obs={obs} summary="max" unit={unit} />
                        <SummaryCell value={stats[middleKey]} obs={obs} summary={middleKey} unit={unit} />
                        <Td isNumeric>{stats.count ?? 0}</Td>
                    </Tr>;
                })}
            </Tbody>
        </Table>
    </Box>;
}

function formatHour(hour) {
    if (hour === 0) {
        return "12:00 AM";
    }
    if (hour === 12) {
        return "12:00 PM";
    }
    return (hour % 12) + ":00 " + (hour < 12 ? "AM" : "PM");
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

function webcamArchiveStamp(date, hour) {
    const [year, month, day] = date.split("-").map(Number);
    const desiredWallTime = Date.UTC(year, month - 1, day, hour);
    const noonUtc = Date.UTC(year, month - 1, day, 12);
    let archiveTime = desiredWallTime - stationOffsetMs(noonUtc);
    archiveTime = desiredWallTime - stationOffsetMs(archiveTime);

    const stationParts = stationDateTimeParts(archiveTime);
    if (Number(stationParts.year) !== year
        || Number(stationParts.month) !== month
        || Number(stationParts.day) !== day
        || Number(stationParts.hour) !== hour) {
        return null;
    }

    const utc = new Date(archiveTime);
    return utc.getUTCFullYear().toString()
        + (utc.getUTCMonth() + 1).toString().padStart(2, "0")
        + utc.getUTCDate().toString().padStart(2, "0")
        + "_"
        + utc.getUTCHours().toString().padStart(2, "0")
        + "00";
}

function HourlyWebcamImage({ date, dateLabel, hour }) {
    const [missing, setMissing] = useState(false);
    const hourLabel = formatHour(hour);
    const archiveStamp = webcamArchiveStamp(date, hour);
    const imageUrl = archiveStamp
        ? "https://rwcweather.com/cumulus/camdump/sky_lg/" + archiveStamp + ".jpg"
        : null;

    return <Box border="1px solid" borderColor="gray.300" borderRadius="md" overflow="hidden" backgroundColor="white">
        {missing || !imageUrl
            ? <Flex aspectRatio="16 / 9" align="center" justify="center" backgroundColor="gray.200" color="gray.600">
                <Text>No archived image</Text>
            </Flex>
            : <ChakraLink href={imageUrl} isExternal display="block" title={"Open " + hourLabel + " image"}>
                <Box
                    as="img"
                    src={imageUrl}
                    alt={"Redwood City webcam at " + hourLabel + " on " + dateLabel}
                    loading="lazy"
                    width="100%"
                    aspectRatio="16 / 9"
                    objectFit="cover"
                    onError={() => setMissing(true)}
                />
            </ChakraLink>}
        <Text px="3" py="2" fontWeight="bold">{hourLabel}</Text>
    </Box>;
}

function HourlyWebcamGallery({ date, dateLabel, isToday, currentHour }) {
    const hours = Array.from({ length: isToday ? currentHour + 1 : 24 }, (_, hour) => hour);

    return <Box mt="6">
        <Heading as="h3" size="3">Hourly webcam</Heading>
        <Text mb="3">Images captured at the start of each hour, in Redwood City local time.</Text>
        <SimpleGrid columns={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="3">
            {hours.map((hour) =>
                <HourlyWebcamImage
                    key={date + "-" + hour}
                    date={date}
                    dateLabel={dateLabel}
                    hour={hour}
                />
            )}
        </SimpleGrid>
    </Box>;
}

export default function DailyReport() {
    const [today, setToday] = useState("");
    const [currentHour, setCurrentHour] = useState(0);
    const [selectedDate, setSelectedDate] = useState("");
    const [obs, setObs] = useState("temp");

    useEffect(() => {
        const currentDate = stationToday();
        setToday(currentDate);
        setCurrentHour(stationHour());
        setSelectedDate(currentDate);
    }, []);

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
            <DailySummary summary={report.summary} />

            <Box mt="6">
                <Heading as="h3" size="3">Daily graph</Heading>
                <Text fontWeight="bold">Variable:</Text>
                <RadioButtonGroup
                    name="daily-graph-variable"
                    value={obs}
                    options={REPORT_OBS_OPTIONS}
                    optFormat={fmatObsOpt}
                    fn={setObs}
                />
                <DailyChart
                    observations={observations}
                    obs={obs}
                    dateLabel={dateLabel}
                    isLoading={isLoading}
                    my="4"
                    mx={{ base: 0, md: 4, xl: 6 }}
                />
            </Box>

            <HourlyWebcamGallery
                date={selectedDate}
                dateLabel={dateLabel}
                isToday={selectedDate === today}
                currentHour={currentHour}
            />
        </>}
    </Page>;
}
