import { Box, Button, Collapse, Link, Spinner, Text } from "@chakra-ui/react";
import { useContext, useState } from "react";
import { FiChevronDown } from "react-icons/fi";
import useSWR from "swr";
import { fetcher } from "./conf";
import { UnitCtx } from "./Page";
import {
  Alerts, Discussion, Periods, RainTotal, StaleNote, fmtRain, fmtTemp, fmtWhen, fmtWind, NWS_HOME, SAFE_HREF, PT,
} from "./forecast";

// 72-hour NWS forecast, summary (today–day 3 periods, QPF, Peninsula highlights) and the full
// San Francisco office Area Forecast Discussion. Reuses the home forecast card helpers.

export function useForecastNws() {
  const { data, error } = useSWR("/api/forecast/nws", fetcher, { refreshInterval: 600000 });
  return { fc: data?.result, error, loading: !data && !error };
}

function hourLabel(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", timeZone: PT }).format(d);
}

function dayHeading(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return new Intl.DateTimeFormat("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: PT }).format(d);
}

function groupHourly(hourly) {
  const groups = [];
  let cur = null;
  (hourly || []).forEach((h) => {
    const day = dayHeading(h.start);
    if (!cur || cur.day !== day) {
      cur = { day, hours: [] };
      groups.push(cur);
    }
    cur.hours.push(h);
  });
  return groups;
}

function HourlyTable({ hourly, unit }) {
  if (!hourly) {
    return <Text fontSize="sm" color="gray.600">Hourly forecast unavailable right now.</Text>;
  }
  if (!hourly.length) {
    return <Text fontSize="sm" color="gray.600">No hourly periods in the next 72 hours.</Text>;
  }
  return <HourlyDisclosure hourly={hourly} unit={unit} />;
}

function HourlyDisclosure({ hourly, unit }) {
  const [open, setOpen] = useState(false);
  return (
    <Box id="forecast-hourly" className="forecast-hourly" mt="3">
      <Button className="forecast-hourly-toggle" variant="ghost" size="sm" fontWeight="bold" px="0"
        onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="forecast-hourly-body"
        rightIcon={<Box as={FiChevronDown} transition="transform 0.2s" transform={open ? "rotate(180deg)" : undefined} />}>
        {open ? "Hide 72-hour hourly forecast" : "Show 72-hour hourly forecast"}
      </Button>
      <Collapse in={open} animateOpacity>
      <Box id="forecast-hourly-body" overflowX="auto" maxH={{ base: "420px", md: "520px" }} overflowY="auto" bg="white" borderRadius="8px">
        {groupHourly(hourly).map((g) => (
          <Box key={g.day} className="forecast-hourly-day" px="2" py="2" borderBottom="1px solid #e2e2e2">
            <Text fontWeight="semibold" fontSize="sm" mb="1">{g.day}</Text>
            {g.hours.map((h) => {
              const rain = h.qpf_mm != null ? fmtRain(unit, h.qpf_mm) : null;
              return (
                <Box key={h.start} className="forecast-hourly-row" fontSize="sm" py="0.5" px="1" borderBottom="1px solid #f0f0f0">
                  <Text as="span" fontWeight="semibold" whiteSpace="nowrap" minW="4.2rem" display="inline-block">{hourLabel(h.start)}</Text>
                  {" "}
                  <Text as="span" whiteSpace="nowrap">{fmtTemp(unit, h.temp_c)}</Text>
                  <Text as="span" color="blue.700"> · {h.pop}%{rain ? " · " + rain : ""}</Text>
                  <Text color="gray.700" noOfLines={2} title={h.detailed || h.short}>
                    {h.short} · {fmtWind(unit, h)}
                  </Text>
                </Box>
              );
            })}
          </Box>
        ))}
      </Box>
      </Collapse>
    </Box>
  );
}


function FullAfdDisclosure({ office, sections }) {
  const [open, setOpen] = useState(false);
  return (
    <Box className="forecast-afd-full" mt="3">
      <Button className="forecast-afd-full-toggle" variant="ghost" size="sm" fontWeight="semibold" px="0"
        onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="forecast-afd-full-body"
        rightIcon={<Box as={FiChevronDown} transition="transform 0.2s" transform={open ? "rotate(180deg)" : undefined} />}>
        {open ? "Hide full discussion" : "Show full discussion (NWS " + (office || "MTR") + ")"}
      </Button>
      <Collapse in={open} animateOpacity>
        <Box id="forecast-afd-full-body" bg="white" borderRadius="8px" p="3">
          {sections.map((s) => (
            <Box key={s.name} className="forecast-afd-section" mb="3">
              <Text fontWeight="bold" fontSize="sm" textTransform="capitalize">
                {s.name.toLowerCase()}
              </Text>
              <Text fontSize="sm" whiteSpace="pre-wrap" color="gray.700" lineHeight="short">{s.body}</Text>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

function FullAfd({ afd, discussion }) {
  const d = afd || discussion;
  if (d == null) {
    return <Text className="forecast-afd-unavailable" fontSize="sm" color="gray.600" mt="2">Forecast discussion unavailable right now.</Text>;
  }
  const url = SAFE_HREF.test(d.url || "") ? d.url : null;
  const sections = d.sections || [];
  return (
    <Box id="forecast-afd" className="forecast-afd" mt="4">
      <Text fontSize={{ base: "md", md: "lg" }} fontWeight="bold" mb="1">Area Forecast Discussion</Text>
      <Discussion d={discussion || { ...d, sections: undefined, product_text: undefined }} />
      {sections.length > 0 && <FullAfdDisclosure office={d.office} sections={sections} />}
      {url && <Text fontSize="xs" mt="2"><Link href={url} isExternal textDecoration="underline">NWS product page</Link></Text>}
    </Box>
  );
}

export function NwsForecastSection() {
  const unit = useContext(UnitCtx);
  const { fc, error, loading } = useForecastNws();
  return (
    <Box id="forecast-nws" className="forecast-section" border="2px solid #656382" bg="gray.100"
      p={{ base: 2, md: 4 }} borderRadius="10px" mb="6">
      <Text fontSize={{ base: "lg", md: "xl" }} mb="1">NWS forecast (72 hours)</Text>
      <Text fontSize="sm" color="gray.700" mb="2">
        Point forecast and Area Forecast Discussion from the National Weather Service San Francisco Bay Area / Monterey office, for the station location.
      </Text>
      {loading && <Spinner size="sm" />}
      {error && !fc && <Text fontSize="sm" color="gray.600">NWS forecast unavailable right now.</Text>}
      {fc && <>
        <StaleNote stale={fc.stale} fetchedAt={fc.fetched_at} />
        <Alerts alerts={fc.alerts} />
        <Periods periods={fc.periods} unit={unit} />
        <RainTotal periods={fc.periods} total={fc.qpf_total_mm} unit={unit} />
        <HourlyTable hourly={fc.hourly} unit={unit} />
        <FullAfd afd={fc.afd} discussion={fc.discussion} />
      </>}
      <Text fontSize="xs" color="gray.600" mt="3">
        <Link href={NWS_HOME} isExternal>National Weather Service</Link> point forecast
        {fc?.updated && <> · updated {fmtWhen(fc.updated)}</>}
      </Text>
    </Box>
  );
}
