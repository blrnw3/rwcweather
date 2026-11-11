import { Box, Grid, Link, Spinner, Text } from '@chakra-ui/react';
import { useContext } from 'react';
import useSWR from "swr";
import { formatObs } from '../format';
import { fetcher } from './conf';
import { UnitCtx } from './Page';

// Nearby-station observations (GET /api/nearby). The backend fetches and caches NWS/IEM (Pulgas, SFO)
// and WeatherLink's public station JSON (Tum Suden, White Oaks, Jasper Ridge). Temperatures are °C and
// rain is mm; they are converted here for the unit toggle. This station's current reading is taken from
// the live dashboard payload already loaded on the home page, so the card does not re-query the DB.

const PT = "America/Los_Angeles";
const SAFE_HREF = /^https:\/\/[^\s"'<>`\\]+$/i;

export function useNearby() {
  const { data, error } = useSWR("/api/nearby", fetcher, { refreshInterval: 600000 });
  return { nearby: data?.result, error, loading: !data && !error };
}

function ageLabel(iso, nowMs) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (isNaN(t)) return null;
  const sec = Math.max(0, Math.round(((nowMs || Date.now()) - t) / 1000));
  if (sec < 45) return "just now";
  if (sec < 120) return "1 min ago";
  if (sec < 3600) return Math.round(sec / 60) + " min ago";
  if (sec < 90 * 60) return "1 h ago";
  if (sec < 36 * 3600) return Math.round(sec / 3600) + " h ago";
  const d = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: PT }).format(new Date(t));
  return d + " PT";
}

function fmtTemp(unit, c, withUnit) {
  if (c == null) return "–";
  return formatObs(unit, c, "temp", false, withUnit);
}

function elevLabel(m, source) {
  if (m == null) return "";
  const approx = source === "estimated" ? "~" : "";
  return approx + Math.round(m) + " m";
}

function StationRow({ s, unit, nowMs }) {
  const href = SAFE_HREF.test(s.url || "") ? s.url : null;
  const name = href
    ? <Link href={href} isExternal textDecoration="underline">{s.name}</Link>
    : s.name;
  const dist = s.id === "rwc" ? "this station" : (s.dist_km != null ? s.dist_km.toFixed(1) + " km" : null);
  const meta = [dist, elevLabel(s.elev_m, s.elev_source)].filter(Boolean).join(" · ");
  const age = ageLabel(s.observed_at, nowMs);
  const stale = s.observed_at && (nowMs - new Date(s.observed_at).getTime() > 2 * 3600 * 1000);
  const sub = [meta, age].filter(Boolean).join(" · ");
  if (!s.available) {
    return <>
      <Box>
        <Text fontWeight="bold" whiteSpace="nowrap">{name}</Text>
        {sub && <Text fontSize="xs" color={stale ? "orange.700" : "gray.600"}>{sub}</Text>}
      </Box>
      <Text className="nearby-no-data" gridColumn="span 3" fontSize="sm" color="gray.600">no recent data</Text>
    </>;
  }
  return <>
    <Box>
      <Text fontWeight="bold" whiteSpace="nowrap">{name}</Text>
      {sub && <Text fontSize="xs" color={stale ? "orange.700" : "gray.600"}>{sub}</Text>}
    </Box>
    <Text whiteSpace="nowrap" fontWeight="semibold">{fmtTemp(unit, s.temp_c, true)}</Text>
    <Text className="nearby-hilo" whiteSpace="nowrap" color="gray.700">
      {s.temp_min_c == null && s.temp_max_c == null ? "–" : fmtTemp(unit, s.temp_min_c, false) + "–" + fmtTemp(unit, s.temp_max_c, false)}</Text>
    <Text whiteSpace="nowrap">{s.rain_today_mm == null ? "–" : formatObs(unit, s.rain_today_mm / 25.4, "rain")}</Text>
  </>;
}

function rwcStation(dash, origin) {
  const now = dash?.now;
  const rainIn = dash?.today?.rain?.total;
  const t = now?.t_obs || now?.t;
  const observed = t != null ? new Date(t).toISOString() : null;
  const has = now?.temp != null || rainIn != null;
  return {
    id: "rwc", name: "Emerald Lake Hills", url: null,
    lat: origin?.lat, lon: origin?.lon, elev_m: origin?.elev_m ?? 125, elev_source: "published",
    dist_km: 0, temp_c: now?.temp ?? null,
    temp_min_c: dash?.today?.temperature?.min_val ?? null,
    temp_max_c: dash?.today?.temperature?.max_val ?? null,
    rain_today_mm: rainIn == null ? null : rainIn * 25.4,
    observed_at: observed, available: !!has,
  };
}

export function NearbyCard({ dash }) {
  const unit = useContext(UnitCtx);
  const { nearby, error, loading } = useNearby();
  const rows = [];
  if (nearby) {
    rows.push(rwcStation(dash, nearby.origin));
    rows.push(...(nearby.stations || []));
  }
  return <Box id="nearby-card" width={{ base: "98%", md: "460px" }} minHeight="250px" border="2px solid #656382" bg="gray.100"
    p={{ base: 2, md: 4 }} my={2} mx={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }} mb="1">Weather nearby</Text>
    {loading && <Spinner size="sm" />}
    {error && !nearby && <Text className="nearby-unavailable" fontSize="sm" color="gray.600">Nearby observations unavailable right now.</Text>}
    {nearby && <Grid id="nearby-stations" templateColumns="1fr auto auto auto" columnGap={{ base: "2", md: "3" }} rowGap="2" fontSize="sm" mt="1" alignItems="baseline">
      <Text fontSize="xs" color="gray.600"></Text>
      <Text fontSize="xs" color="gray.600">Temp</Text>
      <Text fontSize="xs" color="gray.600" whiteSpace="nowrap">Lo–Hi</Text>
      <Text fontSize="xs" color="gray.600" whiteSpace="nowrap">Rain today</Text>
      {rows.map((s) => <StationRow key={s.id} s={s} unit={unit} nowMs={Date.now()} />)}
    </Grid>}
    <Text fontSize="xs" color="gray.600" mt="2">
      Pulgas Ridge and SFO from the NWS and the Iowa Environmental Mesonet; Tum Suden, White Oaks and Jasper Ridge from WeatherLink public pages.
    </Text>
  </Box>;
}
