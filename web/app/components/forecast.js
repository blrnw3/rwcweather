import { Box, Button, Collapse, Grid, Link, ListItem, Spinner, Text, UnorderedList } from '@chakra-ui/react';
import { useContext, useState } from 'react';
import { FiChevronDown } from "react-icons/fi";
import useSWR from "swr";
import { convFunction, unitForObsType } from '../format';
import { fetcher } from './conf';
import { UnitCtx } from './Page';

// NWS forecast card (GET /api/forecast). The backend fetches and caches api.weather.gov (forecast for the station's
// grid point, the San Francisco office's Area Forecast Discussion and active alerts for the point) and sends
// temperatures in °C and wind in mph, the site's base units; they are converted to the visitor's unit choice here.
// Each part can be null when NWS is unavailable, and the card then says so for that part only.

const PT = "America/Los_Angeles";
const SAFE_HREF = /^https:\/\/[^\s"'<>`\\]+$/i;
const NWS_HOME = "https://forecast.weather.gov/MapClick.php?lat=37.47&lon=-122.265";

export function useForecast() {
  const { data, error } = useSWR("/api/forecast", fetcher, { refreshInterval: 600000 });
  return { fc: data?.result, error, loading: !data && !error };
}

function fmtTemp(unit, c) {
  if (c == null) return "–";
  return Math.round(convFunction(unit, "temp")(c)) + unitForObsType(unit, "temp");
}

function fmtWind(unit, p) {
  if (p.wind_mph_hi == null) return "–";
  if (p.wind_mph_hi === 0) return "Calm";
  const conv = convFunction(unit, "wind");
  const lo = Math.round(conv(p.wind_mph_lo)), hi = Math.round(conv(p.wind_mph_hi));
  return (p.wind_dir ? p.wind_dir + " " : "") + (lo === hi ? hi : lo + "–" + hi) + " " + unitForObsType(unit, "wind");
}

export function fmtWhen(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  return new Intl.DateTimeFormat("en-US", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: PT })
    .format(d) + " PT";
}

const ALERT_COLOURS = {
  Extreme: { bg: "red.600", color: "white" },
  Severe: { bg: "red.500", color: "white" },
  Moderate: { bg: "orange.300", color: "gray.900" },
  Minor: { bg: "yellow.200", color: "gray.900" },
};

function Alerts({ alerts }) {
  if (alerts == null) {
    return <Text className="forecast-alerts-unavailable" fontSize="xs" color="gray.600">Alerts unavailable right now.</Text>;
  }
  if (alerts.length === 0) {
    return <Text className="forecast-no-alerts" fontSize="xs" color="gray.600">No active alerts</Text>;
  }
  return alerts.map((a, i) => {
    const c = ALERT_COLOURS[a.severity] || ALERT_COLOURS.Minor;
    const until = fmtWhen(a.ends);
    return <Box key={i} className="forecast-alert" role="alert" bg={c.bg} color={c.color} borderRadius="6px" px="2" py="1" mb="1"
      fontSize="sm" title={a.description || a.headline}>
      <Text as="span" fontWeight="bold">⚠ {a.event}</Text>
      {until && <Text as="span"> · until {until}</Text>}
      {a.headline && a.headline !== a.event && <Text fontSize="xs" noOfLines={2}>{a.headline}</Text>}
    </Box>;
  });
}

function Periods({ periods, unit }) {
  if (!periods) {
    return <Text className="forecast-unavailable" fontSize="sm" color="gray.600" my="2">Forecast unavailable right now.</Text>;
  }
  if (periods.length === 0) {
    return <Text fontSize="sm" color="gray.600" my="2">No forecast periods yet.</Text>;
  }
  // Desktop: name | short forecast | temp | rain · wind on one line. Mobile: the short forecast drops to its own
  // line under the numbers (CSS order), so neither gets squeezed.
  return <Grid id="forecast-periods" templateColumns={{ base: "auto auto 1fr", md: "auto 1fr auto auto" }}
    columnGap="2" rowGap={{ base: "0", md: "1" }} fontSize="sm" mt="1" alignItems="baseline">
    {periods.map((p, i) => [
      <Text key={p.start + "n"} order={i * 4} fontWeight="bold" whiteSpace="nowrap" mt={{ base: i ? 1 : 0, md: 0 }}>{p.name}</Text>,
      <Text key={p.start + "s"} order={{ base: i * 4 + 3, md: i * 4 + 1 }} gridColumn={{ base: "1 / -1", md: "auto" }}
        title={p.detailed} noOfLines={1} color={{ base: "gray.700", md: "inherit" }}>{p.short}</Text>,
      <Text key={p.start + "t"} order={{ base: i * 4 + 1, md: i * 4 + 2 }} whiteSpace="nowrap" title={p.is_daytime ? "High" : "Low"}
        color={p.is_daytime ? "red.700" : "blue.700"}>{p.is_daytime ? "Hi " : "Lo "}{fmtTemp(unit, p.temp_c)}</Text>,
      <Text key={p.start + "w"} order={{ base: i * 4 + 2, md: i * 4 + 3 }} whiteSpace="nowrap" color="gray.700"
        title="Chance of precipitation · wind">💧{p.pop}% · {fmtWind(unit, p)}</Text>,
    ])}
  </Grid>;
}

function Discussion({ d }) {
  const [isOpen, setOpen] = useState(false);
  if (d == null) {
    return <Text className="forecast-afd-unavailable" fontSize="xs" color="gray.600" mt="2">Forecast discussion unavailable right now.</Text>;
  }
  const hasMore = (d.local?.length || 0) > 0 || d.short_term || d.long_term || d.synopsis;
  const url = SAFE_HREF.test(d.url || "") ? d.url : null;
  return <Box id="forecast-discussion" mt="2" fontSize="sm">
    <Text fontWeight="bold">
      Forecast discussion
      {hasMore && <Button className="forecast-afd-toggle" variant="ghost" size="xs" minW="auto" h="auto" px="1" py="0" ml="1"
        verticalAlign="baseline" fontWeight="normal" color="gray.600" onClick={() => setOpen(!isOpen)}
        aria-expanded={isOpen} aria-controls="forecast-afd-details"
        aria-label={isOpen ? "Hide discussion details" : "Show discussion details"} title={isOpen ? "Hide details" : "More from the discussion"}>
        <Box as={FiChevronDown} transition="transform 0.2s" transform={isOpen ? "rotate(180deg)" : undefined} />
      </Button>}
    </Text>
    {d.key_messages?.length > 0
      ? <UnorderedList className="forecast-key-messages" ml="4" spacing="0" lineHeight="short">
        {d.key_messages.map((m, i) => <ListItem key={i}>{m}</ListItem>)}
      </UnorderedList>
      : !isOpen && d.short_term && <Text noOfLines={2} lineHeight="short">{d.short_term}</Text>}
    <Collapse in={isOpen} animateOpacity>
      <Box id="forecast-afd-details" className="forecast-afd-details" color="gray.700" lineHeight="short" mt="1">
        {d.local?.length > 0 && <>
          <Text fontWeight="bold" fontSize="xs" mt="1">Bay Area mentions</Text>
          {d.local.map((s, i) => <Text key={i} fontSize="xs">“{s}”</Text>)}
        </>}
        {d.synopsis && <><Text fontWeight="bold" fontSize="xs" mt="1">Synopsis</Text><Text fontSize="xs">{d.synopsis}</Text></>}
        {d.short_term && <><Text fontWeight="bold" fontSize="xs" mt="1">Short term</Text><Text fontSize="xs">{d.short_term}</Text></>}
        {d.long_term && <><Text fontWeight="bold" fontSize="xs" mt="1">Long term</Text><Text fontSize="xs">{d.long_term}</Text></>}
        {url && <Text fontSize="xs" mt="1"><Link href={url} isExternal textDecoration="underline">Full discussion</Link> (NWS {d.office})</Text>}
      </Box>
    </Collapse>
    {d.issued && <Text fontSize="xs" color="gray.600">Discussion issued {fmtWhen(d.issued)}</Text>}
  </Box>;
}

export function ForecastCard() {
  const unit = useContext(UnitCtx);
  const { fc, error, loading } = useForecast();
  return <Box id="forecast-card" width={{ base: "98%", md: "460px" }} minHeight="250px" border="2px solid #656382" bg="gray.100"
    p={{ base: 2, md: 4 }} my={2} mx={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }} mb="1">Forecast</Text>
    {loading && <Spinner size="sm" />}
    {error && !fc && <Text className="forecast-unavailable" fontSize="sm" color="gray.600">Forecast unavailable right now.</Text>}
    {fc && <>
      <Alerts alerts={fc.alerts} />
      <Periods periods={fc.periods} unit={unit} />
      <Discussion d={fc.discussion} />
    </>}
    <Text fontSize="xs" color="gray.600" mt="2">
      <Link href={NWS_HOME} isExternal>National Weather Service</Link> point forecast
      {fc?.updated && <> &middot; updated {fmtWhen(fc.updated)}</>}
    </Text>
  </Box>;
}
