import {
  Box, Button, Collapse,
  Flex, Grid, Heading, Link, Spinner, Text,
  Tooltip,
  useDisclosure, useRadioGroup, Image
} from '@chakra-ui/react';
import { useContext, useEffect, useRef, useState } from 'react';
import { IconContext } from "react-icons";
import { GiDew } from "react-icons/gi";
import { FiChevronDown, FiWind } from "react-icons/fi";
import { ImArrowDown, ImArrowUp } from "react-icons/im";
import { IoTelescopeOutline } from "react-icons/io5";
import { RiHazeLine } from "react-icons/ri";
import { VscCircleFilled, VscDash } from "react-icons/vsc";
import { WiBarometer, WiDaySunny, WiHumidity, WiRain, WiThermometer } from "react-icons/wi";
import useSWR from "swr";
import { LatestChart, SummaryChart } from '../components/chart';
import { YearChart } from '../components/yearChart';
import { fetcher, fmatObsOptIcon, fmatTimeOpt, OBS, RAIN_VIEW_NAMES, RAIN_VIEWS, SUN_VIEW_NAMES, SUN_VIEWS, WIND_SUMMARY_NAMES, WIND_SUMMARY_VIEWS } from '../components/conf';
import { Page, UnitCtx } from "../components/Page";
import { SunRibbon, useSunDay, fmtDaylightDelta } from '../components/sun';
import { WetRibbon } from '../components/wet';
import RadioCard from '../components/RadioCard';
import { RecapCard } from '../components/recap';
import { aqiStatus, formatObs, moonPhase, prettySecs, timeOf } from '../format';
import {
  CLIMATE_PAGE, ClimateAnom, annualNormal, dailyNormal, monthlyNormal,
  periodToDateTempNormal, periodToDateTotalNormal, signedPctDeparture,
  waterYearNormal, waterYearNormalToDate,
} from '../components/climate';
import {
  RECORD, TIE, ON_TRACK,
  hottestHigh, coldestLow, warmestLow, coldestHigh, localHourFromServer,
} from '../lib/recordFlags';
import React from 'react';
import { LIVE_SWR, useLivePoll } from '../components/liveRefresh';

let isLoading = true;
let errCount = 0;
let goodData;
let lastObs;
let unit;
let updateCount = 0;

function useDashboard(props) {
  let updateInterval = updateCount < 10 ? 3000 : 9000;
  const { data, error, isValidating, revalidate } = useSWR(`/api/web/dashboard/live`, fetcher, LIVE_SWR);
  useLivePoll(`/api/web/dashboard/live`, revalidate, updateInterval);
  isLoading = true;
  if (error || !data) {
    console.log(error);
    if (goodData) {
      errCount += 1;
      return goodData;
    }
    return error ? 0 : null;
  }
  let res = data["result"];
  res["server"] = data["server"];

  // let obsSummary = new Map();
  let obsChange = new Map();
  let currObs = res["now"];

  for (let k in currObs) {
    obsChange.set(k, null);
    if (lastObs && lastObs[k] != currObs[k]) {
      obsChange.set(k, currObs[k] > lastObs[k]);
    }
  }
  // console.log(obsChange);
  lastObs = currObs;

  res["obs_change"] = obsChange;
  goodData = res;
  errCount = 0;
  if (!isValidating) {
    updateCount++;
  }
  isLoading = isValidating;
  return res;
}

// export async function getStaticProps() {
//   // `getStaticProps` is invoked on the server-side,
//   // so this `fetcher` function will be executed on the server-side.
//   // const live = await fetcher("/api/web/dashboard/live");
//   const live = {};
//   return {
//     props: {
//       live: live,
//     },
//     revalidate: 60, // In seconds
//   }
// }

function useSummary() {
  const { data, error, revalidate } = useSWR(`/api/web/dashboard/summary`, fetcher, LIVE_SWR);
  useLivePoll(`/api/web/dashboard/summary`, revalidate, 300000, { minAgeMs: 30000 });
  if (error || !data) {
    console.log(error);
    return error ? 0 : null;
  }
  let res = data["result"];
  res["server"] = data["server"];

  return res;
}

function LiveTime(props) {
  const dash = props.dash;
  // const [status, setStatus] = useState("gray");

  // useEffect(() => {
  //   setStatus("blue")
  //   const interval = setInterval(() => {
  //     setStatus("purple");
  //   }, 1000);
  // });

  const dt_fmat = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short", timeZone: "America/Los_Angeles" })
  let t = "Loading...";
  let status = "blue";
  if (dash === 0) {
    t = "Error getting data... retrying";
    status = "red";
  }
  if (dash) {
    let t_dt = new Date(dash["now"]["t_obs"]);
    let t_dt_fmt = dt_fmat.format(t_dt).replace("GMT-7", "PDT").replace("GMT-8", "PST");
    let t_server = new Date(dash["server"]["datetime"]);
    let diff = Math.round((t_server - t_dt) / 1000);
    if (diff > 100) {
      t = "Delayed: " + t_dt_fmt + " (" + diff + "s old)";
      status = "orange";
    } else {
      t = "Live: " + t_dt_fmt + " (" + diff + "s ago)";
      status = "#4b4";
    }
    if (errCount > 0) {
      t += ". Last update failed. Retrying. Error count: " + errCount;
      status = "orange";
    }
  }

  let icon = isLoading ? <Spinner size="sm" speed="1s" color={status} /> : <IconContext.Provider value={{ color: status, size: "1.6em", style: { display: "block" } }} >
    <VscCircleFilled /></IconContext.Provider>
  return <Flex align="center" gap="2">
    <Box width="30px" height="30px" display="flex" alignItems="center" justifyContent="center" flexShrink="0">{icon}</Box>
    <Text>{t}</Text>
  </Flex>;
}

function LiveDate(props) {
  const dash = props.dash;
  const dt_fmat = new Intl.DateTimeFormat("en-US", { day: "2-digit", month: "long", year: "numeric", weekday: "long", timeZone: "America/Los_Angeles" })
  let t = "Loading...";
  if (dash) {
    let t_dt = new Date(dash["now"]["t_obs"]);
    t = dt_fmat.format(t_dt);
  }
  return t;
}

function HomeCard(props) {
  let color = "#454332";
  if (props.changed != null) {
    color = props.changed ? "#459332" : "#954332";
  }
  let border = "1px solid " + color;
  return <Box minWidth="300px" border={border} bg="gray.100" p="3" m={{ base: 1, md: 2 }} borderRadius="12">
    {props.children}
  </Box>
}

// Station-local calendar date [y, m, d] from the API's server block.
function serverDate(...sources) {
  for (const src of sources) {
    if (src?.server?.date) {
      return src.server.date;
    }
  }
  return null;
}

// Outside daylight: "twilight" between civil dawn and sunrise or sunset and civil dusk (sun 0° to -6°),
// "dark" otherwise; null in daylight (or without astronomy times). Uses today's suncalc times from the summary.
function nightPhase(astro, nowMs) {
  if (!astro?.sunrise || !astro?.sunset || nowMs == null) return null;
  if (nowMs >= astro.sunrise && nowMs <= astro.sunset) return null;
  const dawn = astro.dawn, dusk = astro.dusk;
  if ((dawn && nowMs >= dawn && nowMs < astro.sunrise) || (dusk && nowMs > astro.sunset && nowMs <= dusk)) return "twilight";
  return "dark";
}

// Optional `normals` = { lo, hi } (DB units) adds a bracketed climate
// comparison after each value, e.g. "Lo: 57.2 °F (+1.3) @ 07:18".
function LoHiCardSection(props) {
  let lo = formatObs(unit, props.hilo?.["min_val"], props.obs);
  let loAt = timeOf(props.hilo?.["min_at"]);
  let hi = formatObs(unit, props.hilo?.["max_val"], props.obs);
  let hiAt = timeOf(props.hilo?.["max_at"]);
  const anom = (value, normal, stat) => props.normals &&
    <ClimateAnom inline value={value} normal={normal} obs={props.obs} stat={stat} unit={unit} />;

  return <Box borderBottom="1px solid #ccc" borderTop="1px solid #ccc" py="1px">
    <Text>Lo: <Text as="span" fontWeight="bold">{lo}</Text>{anom(props.hilo?.["min_val"], props.normals?.lo, "min")} @ {loAt}</Text>
    <Text>Hi: <Text as="span" fontWeight="bold">{hi}</Text>{anom(props.hilo?.["max_val"], props.normals?.hi, "max")} @ {hiAt}</Text>
  </Box>
}

function TrendArrow(props) {
  let rawChange60 = (props.trends?.["0"]?.[props.obs] || 0) - (props.trends?.["60"]?.[props.obs] || 0)
  let change60 = formatObs(unit, rawChange60, props.obs_conv, true, false);

  let arrow = <VscDash />;
  let arrowColor = "blue";
  let arrowSize = "1em";
  if (rawChange60 != 0) {
    arrow = (rawChange60 > 0) ? <ImArrowUp /> : <ImArrowDown />;  // TODO: big vs small
    arrowColor = (rawChange60 > 0) ? "green" : "red";
  }
  return <Box as="span">
    <IconContext.Provider value={{ color: arrowColor, size: arrowSize, style: { display: "inline", paddingRight: "2" } }}>{arrow}</IconContext.Provider>
    {change60} /hr
  </Box>
}
function TrendArrow24hr(props) {
  let rawChange = (props.trends?.["0"]?.[props.obs] || 0) - (props.trends?.["1440"]?.[props.obs] || 0)
  let change = formatObs(unit, rawChange, props.obs_conv, true, false);

  let arrow = <VscDash />;
  let arrowColor = "blue";
  let arrowSize = "1em";
  if (rawChange != 0) {
    arrow = (rawChange > 0) ? <ImArrowUp /> : <ImArrowDown />;  // TODO: big vs small
    arrowColor = (rawChange > 0) ? "green" : "red";
  }
  return <Box as="span">
    Trend: <Text as="span" fontWeight="bold">{change}</Text> from 24hrs ago
    <IconContext.Provider value={{ color: arrowColor, size: arrowSize, style: { display: "inline", marginLeft: "5", paddingLeft: "2" } }}>{arrow}</IconContext.Provider>
  </Box>
}

function YesterdayRange(props) {
  let yestLo = formatObs(unit, props.summary?.["yesterday"]?.[props.name]["min_val"], props.fmat);
  let yestHi = formatObs(unit, props.summary?.["yesterday"]?.[props.name]["max_val"], props.fmat);
  return <Text marginTop="1" >
    Yesterday: <Text as="span" fontWeight="bold">{yestLo}</Text> {"->"} <Text as="span" fontWeight="bold">{yestHi}</Text>
  </Text>
}

function AboutHomeCard() {
  return <Box id="about-home-card" width={{ base: "98%", md: "460px" }} minHeight="250px" border="2px solid #656382" bg="gray.100" p={{ base: 2, md: 4 }} my={2} mx={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }} mb="2">About RWC Weather</Text>
    <Text fontSize="sm" mb="2">
      RWC Weather is an amateur-run personal weather station in Redwood City, California, collecting data continuously since November 2020.
    </Text>
    <Text fontSize="sm" mb="2">
      The station sits ~125 m (420 ft) above sea level in Emerald Hills between Redwood City and Woodside. We experience generally milder nights than the valleys below, protection from westerly winds, and much less summer fog than the coast.
     
    </Text>
    <Text fontSize="sm" mb="2">
      Powered by a wireless Davis VP2 with WeatherLink Live running Cumulus software, a Python Flask backend, and a Next.js / React frontend.
    </Text>
    <Text fontSize="sm">
      <Link href="/about">More about the station &rarr;</Link>
    </Text>
  </Box>;
}

const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function RecordDot({ status }) {
  if (!status) return null;
  const color = status === RECORD ? "red.500" : status === TIE ? "orange.400" : "blue.400";
  const title = status === RECORD ? "Record" : status === TIE ? "Tie" : "On track";
  return <Box as="span" className={"record-dot record-dot-" + status} title={title}
    display="inline-block" w="6px" h="6px" borderRadius="full" bg={color} ml="1" mb="2px" verticalAlign="middle" />;
}

function rainFreqLabel(freq) {
  if (!freq || freq.n == null || freq.n === 0 || freq.pct == null) return "–";
  return freq.pct + "% wet";
}

function DayClimateExtremesCard(props) {
  const date = serverDate(props.dash, props.summary);
  const doy = props.summary?.day_of_year;
  const dateLabel = date ? MONTH_SHORT[date[1] - 1] + " " + date[2] : "today";
  const normMin = date ? dailyNormal("temp", "min", ...date) : null;
  const normMax = date ? dailyNormal("temp", "max", ...date) : null;
  const normAvg = date ? dailyNormal("temp", "avg", ...date) : null;
  const normSun = date ? dailyNormal("sun", "total", ...date) : null;
  const todayTemp = props.dash?.today?.temperature;
  const hour = localHourFromServer(props.summary) ?? localHourFromServer(props.dash);
  const flagHotMax = hottestHigh(todayTemp?.max_val, doy?.temp_max?.max_val);
  const flagColdMin = coldestLow(todayTemp?.min_val, doy?.temp_min?.min_val);
  const flagWarmMin = warmestLow(todayTemp?.min_val, doy?.temp_min?.max_val, hour);
  const flagColdMax = coldestHigh(todayTemp?.max_val, doy?.temp_max?.min_val, hour);

  const fmtExt = (entry, key, fmat, flag) => {
    const val = entry?.[key + "_val"];
    if (val == null) {
      return "–";
    }
    const yr = entry?.[key + "_yr"] ?? entry?.[key + "_at"]?.[0];
    // Keep value (+ year) and record dot on one line so the dot never wraps alone.
    return <Text as="span" className="record-ext" whiteSpace="nowrap">
      {formatObs(unit, val, fmat)}
      {yr ? <Text as="span" fontSize="xs" color="gray.600"> ({yr})</Text> : null}
      <RecordDot status={flag} />
    </Text>;
  };

  const recYr = (entry, key) => entry?.[key + "_yr"] ?? entry?.[key + "_at"]?.[0];
  const notes = [];
  const pushNote = (status, kind, todayVal, recEntry, recKey) => {
    if (!status || todayVal == null || recEntry?.[recKey + "_val"] == null) return;
    const todayS = formatObs(unit, todayVal, "temp");
    const recS = formatObs(unit, recEntry[recKey + "_val"], "temp");
    const yr = recYr(recEntry, recKey);
    const yrBit = yr != null ? " (" + yr + ")" : "";
    if (status === RECORD) notes.push({ status, text: "Record " + kind + ": " + todayS + " beats " + recS + yrBit });
    else if (status === TIE) notes.push({ status, text: "Tie " + kind + ": " + todayS + " matches " + recS + yrBit });
    else notes.push({ status, text: "On track for " + kind + ": " + todayS + " vs " + recS + yrBit });
  };
  pushNote(flagHotMax, "hot high", todayTemp?.max_val, doy?.temp_max, "max");
  pushNote(flagColdMax, "cold high", todayTemp?.max_val, doy?.temp_max, "min");
  pushNote(flagColdMin, "cold low", todayTemp?.min_val, doy?.temp_min, "min");
  pushNote(flagWarmMin, "warm low", todayTemp?.min_val, doy?.temp_min, "max");

  return <Box id="day-climate-extremes-card" width={{ base: "98%", md: "460px" }} minHeight="250px" border="2px solid #656382" bg="gray.100" p={{ base: 2, md: 4 }} my={2} mx={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }}>Climate &amp; extremes for {dateLabel}</Text>
    <Grid id="day-climate-extremes"
      templateColumns="1.4fr repeat(3, 1fr)"
      templateRows="28px auto"
      rowGap="1.5"
      fontSize="sm"
      overflow="auto"
      mt="1">
      <Box></Box>
      <Box fontWeight="bold">Normal</Box>
      <Box fontWeight="bold">Record Low</Box>
      <Box fontWeight="bold">Record High</Box>

      <Box fontWeight="bold">Temp High</Box>
      <Box>{formatObs(unit, normMax, "temp")}</Box>
      <Box>{fmtExt(doy?.temp_max, "min", "temp", flagColdMax)}</Box>
      <Box>{fmtExt(doy?.temp_max, "max", "temp", flagHotMax)}</Box>

      <Box fontWeight="bold">Temp Low</Box>
      <Box>{formatObs(unit, normMin, "temp")}</Box>
      <Box>{fmtExt(doy?.temp_min, "min", "temp", flagColdMin)}</Box>
      <Box>{fmtExt(doy?.temp_min, "max", "temp", flagWarmMin)}</Box>

      <Box fontWeight="bold">Temp Mean</Box>
      <Box>{formatObs(unit, normAvg, "temp")}</Box>
      <Box>{fmtExt(doy?.temp_avg, "min", "temp")}</Box>
      <Box>{fmtExt(doy?.temp_avg, "max", "temp")}</Box>

      <Box fontWeight="bold">Rainfall</Box>
      <Box title="Share of past years with ≥0.01 in on this date">{rainFreqLabel(doy?.rain_freq)}</Box>
      <Box>–</Box>
      <Box>{fmtExt(doy?.rain_total, "max", "rain")}</Box>

      <Box fontWeight="bold">Sunshine</Box>
      <Box>{formatObs(unit, normSun, "sun")}</Box>
      <Box>{fmtExt(doy?.sun_total, "min", "sun")}</Box>
      <Box>{fmtExt(doy?.sun_total, "max", "sun")}</Box>

      <Box fontWeight="bold">Max Gust</Box>
      <Box>–</Box>
      <Box>–</Box>
      <Box>{fmtExt(doy?.gust_max, "max", "gust")}</Box>
    </Grid>
    {notes.length > 0 && <Box id="day-climate-record-notes" mt="2" fontSize="xs" color="gray.700">
      {notes.map((n) => (
        <Text key={n.text} className={"record-note record-note-" + n.status}>
          <Box as="span" display="inline-block" w="6px" h="6px" borderRadius="full" mr="1.5" mb="1px"
            bg={n.status === RECORD ? "red.500" : n.status === TIE ? "orange.400" : "blue.400"} verticalAlign="middle" />
          {n.text}
        </Text>
      ))}
    </Box>}
    <Text fontSize="xs" color="gray.600" mt="2">
      <Link href={CLIMATE_PAGE}>Climate normals</Link> &middot; Records since Nov 2020
      {" "}&middot; Rain normal is % of years with measurable rain (≥0.01 in) on this date
    </Text>
  </Box>;
}
function todayTempNormals(date) {
  if (!date) {
    return null;
  }
  return { lo: dailyNormal("temp", "min", ...date), hi: dailyNormal("temp", "max", ...date) };
}

function TemperatureHomeCard(props) {
  const dash = props.dash;
  const icon = <Text as="span" color="red" className="home_ico"><WiThermometer /></Text>
  let temp = formatObs(unit, dash?.["now"]?.["temp"], "temp");
  let feels = formatObs(unit, dash?.["now"]?.["feels"], "temp");
  let changed = dash ? dash["obs_change"].get("temp") : null;
  let feelsIco = dash?.["now"]?.["feels"] > dash?.["now"]?.["temp"] ? "🥵" : (dash?.["now"]?.["feels"] < dash?.["now"]?.["temp"] ? "🥶" : "");

  return <HomeCard changed={changed}>
    <Text>
      {icon}
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} paddingRight="4">{temp}</Text>
      <TrendArrow trends={dash?.trends} obs="temp" obs_conv="abs_temp" />
    </Text>
    <Text marginBottom="1">
      Feels like <Text as="span" fontWeight="bold">{feels}</Text><Text as="span" paddingLeft="2">{feelsIco}</Text>
    </Text>
    <LoHiCardSection hilo={dash?.today?.temperature} obs="temp" normals={todayTempNormals(serverDate(dash, props.summary))} />
    <YesterdayRange summary={props.summary} name="temperature" fmat="temp" />
    <TrendArrow24hr trends={dash?.trends} obs="temp" obs_conv="abs_temp" />
  </HomeCard>
}

function HumidityHomeCard(props) {
  const dash = props.dash;
  const icon = <Text as="span" color="green" className="home_ico"><WiHumidity /></Text>
  let now = formatObs(unit, dash?.["now"]?.["humi"], "humi");
  let changed = dash ? dash["obs_change"].get("humi") : null;

  return <HomeCard changed={changed}>
    <Text marginBottom="0.8em">
      {icon}
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} paddingRight="4" paddingLeft="1">{now}</Text>
      <TrendArrow trends={dash?.trends} obs="humi" obs_conv="humi" />
    </Text>
    <LoHiCardSection hilo={dash?.today?.humidity} obs="humi" />
    <YesterdayRange summary={props.summary} name="humidity" fmat="humi" />
    <TrendArrow24hr trends={dash?.trends} obs="humi" obs_conv="humi" />
  </HomeCard>
}

function WindHomeCard(props) {
  const dash = props.dash;
  let wind = formatObs(unit, dash?.["now"]?.["wind"], "wind");
  let wdir = formatObs(unit, dash?.["now"]?.["wdir"], "wdir");
  let gust = formatObs(unit, dash?.["now"]?.["gust"], "gust");

  let hi = formatObs(unit, dash?.today?.gust_speed?.["max_val"], "gust");
  let hiAt = timeOf(dash?.today?.gust_speed?.["max_at"]);

  let avgWind = formatObs(unit, dash?.today?.wind_speed?.["avg"], "wind");
  let avgWdir = formatObs(unit, dash?.today?.wind_direction?.["avg"], "wdir");
  let yestAvg = formatObs(unit, props.summary?.["yesterday"]?.["wind_speed"]["avg"], "wind");

  let changed = dash ? dash["obs_change"].get("wind") : null;

  return <HomeCard changed={changed}>
    <Text>
      <Text as="span" color="brown" className="home_ico_sml"><FiWind /></Text>
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} paddingRight="4" paddingLeft="2">{wind}</Text>
      <Text as="span" fontSize={{ base: "xl", md: "2xl" }} paddingRight="1">{wdir}</Text>
    </Text>
    <Text marginBottom="1" borderBottom="1px solid #ccc">
      Gusting <Text as="span" fontSize={{ base: "xl", md: "2xl" }}>{gust}</Text>
    </Text>
    <Text>
      Max gust: <Text as="span" fontWeight="bold">{hi}</Text> @ {hiAt}
    </Text>
    <Text borderBottom="1px solid #ccc">
      Avg wind: <Text as="span" fontWeight="bold">{avgWind}</Text> {avgWdir}
    </Text>
    <Text marginTop="1" >
      Yesterday avg: <Text as="span" fontWeight="bold">{yestAvg}</Text>
    </Text>
  </HomeCard>
}

function RainHomeCard(props) {
  const dash = props.dash;
  let changed = dash ? dash["obs_change"].get("rain") : null;
  let now = formatObs(unit, dash?.["now"]?.["rain"], "rain");
  let rn10 = formatObs(unit, dash?.["rain_trend"]?.["m10"], "rain");
  let rnhr = formatObs(unit, dash?.["rain_trend"]?.["hr1"], "rain");
  const show10m = dash?.["rain_trend"]?.["hr1"] > 0;
  let rn24 = formatObs(unit, dash?.["rain_trend"]?.["hr24"], "rain");
  let monthly = formatObs(unit, props.summary?.["month"]?.["rain_total"]?.["total"], "rain");
  let annual = formatObs(unit, props.summary?.["year"]?.["rain_total"]?.["total"], "rain");
  let water_yr = formatObs(unit, props.summary?.["water_year"]?.["rain_total"]?.["total"], "rain");
  const monthTotal = props.summary?.["month"]?.["rain_total"]?.["total"];
  const wyTotal = props.summary?.["water_year"]?.["rain_total"]?.["total"];
  const date = serverDate(props.summary, dash);
  let last = dash ? prettySecs(new Date(dash["now"]["t"]) - new Date(dash["last_rain"])) : "-";

  const wetDisc = useDisclosure();
  const icon = <Text as="span" color="blue" className="home_ico"><WiRain /></Text>
  return <HomeCard changed={changed}>
    <Text>
      <Tooltip label="Rainfall">{icon}</Tooltip>
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} paddingRight="4" paddingLeft="1">{now}</Text>
      <WetHoursInline wet={dash?.wet} rainToday={dash?.["now"]?.["rain"]} isOpen={wetDisc.isOpen} onToggle={wetDisc.onToggle} />
    </Text>
    <WetHoursDetails wet={dash?.wet} rainToday={dash?.["now"]?.["rain"]} isOpen={wetDisc.isOpen} nowMs={dash?.server?.epoch ? dash.server.epoch * 1000 : null} />
    {/* "Past 10m" only matters while it's raining: show it only if there was rain in the past hour. */}
    <Text borderBottom={show10m ? null : "1px solid #ccc"}>Last rain: <Text as="span" fontWeight="bold">{last}</Text> ago</Text>
    {show10m && <Text borderBottom="1px solid #ccc" className="rain-past-10m">Past 10m: <Text as="span" fontWeight="bold">{rn10}</Text></Text>}
    <Text>Hourly: <Text as="span" fontWeight="bold">{rnhr}</Text></Text>
    <Text borderBottom="1px solid #ccc">Past 24hrs: <Text as="span" fontWeight="bold">{rn24}</Text></Text>
    <Text>
      Monthly: <Text as="span" fontWeight="bold">{monthly}</Text>
      {date && <ClimateAnom inline value={monthTotal} normal={monthlyNormal("rain", "total", date[1])} obs="rain" stat="total" unit={unit} />}
    </Text>
    <WaterYearLine value={water_yr} total={wyTotal} date={date} />
  </HomeCard>
}

// Derived wet hours today, inline next to today's rain so the card keeps its height; hidden on dry days.
// The chevron expands spells, longest spell and rate (WetHoursDetails), like the water-year line.
const wetShown = (wet, rainToday) => wet && rainToday > 0 && wet.wet_h > 0;

function WetHoursInline({ wet, rainToday, isOpen, onToggle }) {
  if (!wetShown(wet, rainToday)) {
    return null;
  }
  return <Text as="span" className="wet-hours" whiteSpace="nowrap">
    <Tooltip label="Wet time today: from 30 min before the first tip of a spell to 30 min after its last (a lone tip counts 30 min)">
      <Text as="span" fontWeight="bold">{formatObs(unit, wet.wet_h, "wet")}</Text>
    </Tooltip> wet
    {wet.wet_now && <Text as="span" ml="2" px="2" py="0.5" borderRadius="8" fontSize="sm" fontWeight="bold" bg="blue.200" color="gray.800" className="wet-now-badge">Raining</Text>}
    <WetToggle isOpen={isOpen} onToggle={onToggle} />
  </Text>;
}

function WetToggle({ isOpen, onToggle }) {
  return <Button className="wet-details-toggle" variant="ghost" size="xs" minW="auto" h="auto" px="1" py="0" ml="1"
    verticalAlign="baseline" fontWeight="normal" color="gray.600"
    onClick={onToggle} aria-expanded={isOpen} aria-controls="wet-hours-details"
    aria-label={isOpen ? "Hide wet-hours details" : "Show wet-hours details"} title={isOpen ? "Hide details" : "Wet spells today"}>
    <Box as={FiChevronDown} transition="transform 0.2s" transform={isOpen ? "rotate(180deg)" : undefined} />
  </Button>;
}

function WetHoursDetails({ wet, rainToday, isOpen, nowMs }) {
  if (!wetShown(wet, rainToday)) {
    return null;
  }
  const rate = wet.rate != null ? formatObs(unit, wet.rate, "rain") + "/h" : "–";
  const pct = wet.day_end ? Math.round(wet.wet_h * 3600000 / (Math.min(nowMs || wet.day_end, wet.day_end) - wet.day_start) * 100) : null;
  return <Collapse in={isOpen} animateOpacity>
    <Box id="wet-hours-details" className="wet-hours-details" fontSize="sm" lineHeight="short" color="gray.700" mb="1">
      <WetRibbon wet={wet} nowMs={nowMs} />
      <Text>{wet.spells} spell{wet.spells === 1 ? "" : "s"}, longest {formatObs(unit, wet.longest_h, "wet")}
        {pct != null && <> · {pct}% of day so far</>} · {rate}</Text>
    </Box>
  </Collapse>;
}

// "Water Year: 0.00 in (0%)" with the percent of the normal expected by today,
// plus a chevron that expands the full comparison (WaterYearClimate). It starts
// collapsed so the rain card stays the same height as its neighbours.
function WaterYearLine({ value, total, date }) {
  const { isOpen, onToggle } = useDisclosure();
  const expected = date ? waterYearNormalToDate("rain", "total", ...date) : null;
  const details = total != null && date != null;
  return <>
    <Text className="water-year-line">
      Water Year: <Text as="span" fontWeight="bold">{value}</Text>
      <ClimateAnom inline value={total} normal={expected >= 0.005 ? expected : null} obs="rain" stat="total" unit={unit} />
      {details && <Button className="wy-details-toggle" variant="ghost" size="xs" minW="auto" h="auto" px="1" py="0" ml="1"
        verticalAlign="baseline" fontWeight="normal" color="gray.600"
        onClick={onToggle} aria-expanded={isOpen} aria-controls="water-year-details"
        aria-label={isOpen ? "Hide water-year climate details" : "Show water-year climate details"}
        title={isOpen ? "Hide details" : "Compare with the water-year normal"}>
        <Box as={FiChevronDown} transition="transform 0.2s" transform={isOpen ? "rotate(180deg)" : undefined} />
      </Button>}
    </Text>
    {details && <Collapse in={isOpen} animateOpacity>
      <Box id="water-year-details">
        <WaterYearClimate total={total} date={date} />
      </Box>
    </Collapse>}
  </>;
}

// Water-year rain to date against (1) the full Oct-Sep normal, as an
// absolute difference, and (2) the normal expected by today's date, as a
// percentage. Early in the water year the expected amount is small, so it is
// shown alongside the percentage; if it is ~0 the percentage is omitted.
function WaterYearClimate({ total, date }) {
  if (total == null || !date) {
    return null;
  }
  const fullNormal = waterYearNormal("rain", "total");
  const expected = waterYearNormalToDate("rain", "total", ...date);
  if (fullNormal == null || expected == null) {
    return null;
  }
  const normalLink = <Link href={CLIMATE_PAGE} textDecoration="underline">normal</Link>;
  return <Text className="water-year-climate" fontSize="sm" lineHeight="short" color="gray.700">
    <span className="wy-vs-full">({formatObs(unit, total - fullNormal, "rain", true)} vs full-year {normalLink})</span>
    <br />
    <span className="wy-vs-to-date">{expected >= 0.005
      ? <>({Math.round(total / expected * 100)}% of {formatObs(unit, expected, "rain")} normal to date)</>
      : <>(normal to date: {formatObs(unit, 0, "rain")})</>}</span>
  </Text>
}

// Webcam sunshine: today's hours so far, % of possible daylight so far, a "Sunny now" badge (only from a fresh,
// classified minute) and today's minute ribbon.
function SunshineHomeCard(props) {
  const dash = props.dash;
  const sun = dash?.sun;
  const { day, now } = useSunDay("", 120000);
  const icon = <Text as="span" color="orange.400" className="home_ico"><WiDaySunny /></Text>
  const hours = sun?.today_h != null ? formatObs(unit, sun.today_h, "sun") : "–";
  const possible = sun ? formatObs(unit, sun.possible_so_far_h, "sun") : "–";
  const monthTotal = props.summary?.["month"]?.["sun_total"]?.["total"];
  const monthPct = props.summary?.["month"]?.["sunpct_avg"]?.["avg"];
  let badge = null;
  const astro = props.summary?.astronomy;
  const nowMs = dash?.server?.epoch ? dash.server.epoch * 1000 : Date.now();
  const night = nightPhase(astro, nowMs);
  // From sunset onward today's sunshine is final, so drop "so far".
  const dayOver = astro?.sunset != null && nowMs > astro.sunset;
  if (night) {
    const twi = night === "twilight";
    badge = <Text as="span" ml="2" px="2" py="0.5" borderRadius="8" fontSize="sm" fontWeight="bold"
      bg={twi ? "purple.200" : "blue.800"} color={twi ? "purple.900" : "blue.50"} className="sun-now-badge">
      {twi ? "Twilight" : "Dark"}
    </Text>;
  } else if (sun?.now) {
    const sunny = sun.now.state === "sun";
    badge = <Text as="span" ml="2" px="2" py="0.5" borderRadius="8" fontSize="sm" fontWeight="bold"
      bg={sunny ? "yellow.300" : "gray.300"} color="gray.800" className="sun-now-badge">
      {sunny ? "Sunny now" : "Not sunny"}
    </Text>;
  }
  return <HomeCard changed={null}>
    <Text marginBottom="0.5em">
      <Tooltip label="Sunshine (from the webcam)">{icon}</Tooltip>
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} paddingRight="2" paddingLeft="1">{hours}</Text>
      {badge}
    </Text>
    <Text borderBottom="1px solid #ccc">
      {dayOver ? "Today" : "Today so far"}: <Text as="span" fontWeight="bold">{sun?.pct_of_possible != null ? sun.pct_of_possible + "%" : "–"}</Text> of {possible} possible
    </Text>
    <Box my="2"><SunRibbon day={day} nowMs={now} height="16px" /></Box>
    <Text borderTop="1px solid #ccc">
      Daylight: <Text as="span" fontWeight="bold">{sun ? formatObs(unit, sun.daylight_h, "sun") : "–"}</Text>
      {fmtDaylightDelta(sun?.daylight_change_s) && <Tooltip label="Change in day length vs yesterday">
        <Text as="span" fontSize="sm" color="gray.600" whiteSpace="nowrap" className="sun-daylight-delta"> ({fmtDaylightDelta(sun.daylight_change_s)})</Text>
      </Tooltip>}
    </Text>
    <Text>Monthly: <Text as="span" fontWeight="bold">{monthTotal != null ? formatObs(unit, monthTotal, "sun") : "–"}</Text>
      {monthPct != null && <Text as="span" fontSize="sm" color="gray.600" className="sun-month-pct"> ({Math.round(monthPct)}% of possible)</Text>}
    </Text>
  </HomeCard>
}

function PressureHomeCard(props) {
  const dash = props.dash;
  const icon = <Text as="span" color="gray" className="home_ico"><WiBarometer /></Text>
  let now = formatObs(unit, dash?.["now"]?.["pres"], "pres");
  let changed = dash ? dash["obs_change"].get("pres") : null;

  return <HomeCard changed={changed}>
    <Text marginBottom="0.8em">
      {icon}
      <Text as="span" fontSize="2xl" paddingRight="2">{now}</Text>
      <TrendArrow trends={dash?.trends} obs="pres" obs_conv="pres" />
    </Text>
    <LoHiCardSection hilo={dash?.today?.pressure} obs="pres" />
    <YesterdayRange summary={props.summary} name="pressure" fmat="pres" />
    <TrendArrow24hr trends={dash?.trends} obs="pres" obs_conv="pres" />
  </HomeCard>
}

function DewPtHomeCard(props) {
  const dash = props.dash;
  const icon = <Text as="span" color="orange" className="home_ico_sml"><GiDew /></Text>
  let now = formatObs(unit, dash?.["now"]?.["dewpt"], "temp");
  let changed = dash ? dash["obs_change"].get("dewpt") : null;

  return <HomeCard changed={changed}>
    <Text marginBottom="0.8em">
      {icon}
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} paddingRight="4" paddingLeft="2">{now}</Text>
      <TrendArrow trends={dash?.trends} obs="dewpt" obs_conv="abs_temp" />
    </Text>
    <LoHiCardSection hilo={dash?.today?.dew_point} obs="temp" />
    <YesterdayRange summary={props.summary} name="dew_point" fmat="temp" />
    <TrendArrow24hr trends={dash?.trends} obs="dewpt" obs_conv="abs_temp" />
  </HomeCard>
}

function AirQualityHomeCard(props) {
  const dash = props.dash;
  const icon = <Text as="span" color="purple" className="home_ico_sml"><RiHazeLine /></Text>
  let now = "AQI " + formatObs(unit, dash?.["now"]?.["aqi"], "aqi");
  let pm2 = formatObs(unit, dash?.["now"]?.["pm2"], "pm2");
  let avg = formatObs(unit, dash?.["today"]?.["aqi"]?.["avg"], "aqi");
  let statusAvg = aqiStatus(dash?.["today"]?.["aqi"]?.["avg"]);
  let statusNow = aqiStatus(dash?.["now"]?.["aqi"]);
  let changed = dash ? dash["obs_change"].get("aqi") : null;
  let pm2Label = "PM 2.5: " + pm2;
  let yestAvg = formatObs(unit, props.summary?.["yesterday"]?.["aqi"]?.["avg"], "aqi");
  let yestAvgStatus = aqiStatus(props.summary?.["yesterday"]?.["aqi"]?.["avg"]);

  return <HomeCard changed={changed}>
    <Text marginBottom="0.8em">
      {icon}
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} pr="1" pl="2"><Tooltip label={pm2Label}>{now}</Tooltip></Text>
      <Tooltip label={statusNow[1]}><Text as="span" pr="3">{statusNow[0]}</Text></Tooltip>
      <TrendArrow trends={dash?.trends} obs="aqi" obs_conv="aqi" />
    </Text>
    <Text>
      Day Avg: <Text as="span" fontWeight="bold" marginRight="2">{avg}</Text>
      <Tooltip label={statusAvg[1]}>{statusAvg[0]}</Tooltip>
    </Text>
    <LoHiCardSection hilo={dash?.today?.aqi} obs="aqi" />
    <Text marginTop="1">
      Yesterday Avg: <Text as="span" fontWeight="bold" mr="2">{yestAvg}</Text>
      <Tooltip label={yestAvgStatus[1]}>{yestAvgStatus[0]}</Tooltip>
    </Text>
  </HomeCard>
}

function AstronomyHomeCard(props) {
  const astro = props.dash?.astronomy;
  let frac = formatObs(unit, astro?.fraction * 100, "humi")
  const icon = <Text as="span" color="black" className="home_ico_sml"><IoTelescopeOutline /></Text>
  let phase = moonPhase(astro?.phase) || ["", ""];

  return <HomeCard changed={null}>
    <Text>
      {icon}
      <Text as="span" fontSize="2xl" paddingRight="1" paddingLeft="1">{frac} full &nbsp;<Tooltip label={phase[0]}>{phase[1]}</Tooltip></Text>
    </Text>
    <Text borderTop="1px solid #ccc">
      Moon rise: <Text as="span" fontWeight="bold">{timeOf(astro?.rise)}</Text>
    </Text>
    <Text>
      Moon set: <Text as="span" fontWeight="bold">{timeOf(astro?.set)}</Text>
    </Text>
  </HomeCard>
}


function SignedPctAnom({ value, normal }) {
  const text = signedPctDeparture(value, normal);
  if (text == null) return null;
  return <Text as="span" className="climate-anom" display="inline" fontSize="sm" lineHeight="short" ml="1" fontWeight="normal"
    title="Signed departure from the climate normal accumulated to date">({text})</Text>;
}

function PeriodRainSunRows({ summary, rainNormal, sunNormal, rainDaysExpected }) {
  const rainTotal = summary?.rain_total?.total;
  const sunTotal = summary?.sun_total?.total;
  const sunPct = summary?.sunpct_avg?.avg;
  const rainDays = summary?.rain_days;
  return <>
    <Box fontWeight="bold">Rainfall</Box>
    <Box title="Driest day">{formatObs(unit, summary?.rain_total?.min_val, "rain")}</Box>
    <Box title="Wettest day">{formatObs(unit, summary?.rain_total?.max_val, "rain")}</Box>
    <Box title="Period total to date">
      {formatObs(unit, rainTotal, "rain")}
      <SignedPctAnom value={rainTotal} normal={rainNormal} />
    </Box>
    <Box fontWeight="bold">Sunshine</Box>
    <Box title="Dullest day">{formatObs(unit, summary?.sun_total?.min_val, "sun")}</Box>
    <Box title="Sunniest day">{formatObs(unit, summary?.sun_total?.max_val, "sun")}</Box>
    <Box title="Period total hours to date">
      {formatObs(unit, sunTotal, "sun")}
      {sunPct != null && <Text as="span" fontSize="xs" color="gray.600"> ({Math.round(sunPct)}% of max)</Text>}
      <SignedPctAnom value={sunTotal} normal={sunNormal} />
    </Box>
    <Box fontWeight="bold">Rain days</Box>
    <Box>–</Box>
    <Box>–</Box>
    <Box title="Days with ≥0.01 in">
      {rainDays?.count != null ? (rainDays.count + (rainDays.of != null ? " of " + rainDays.of : "")) : "–"}
      {rainDaysExpected != null && rainDays?.count != null && (
        <SignedPctAnom value={rainDays.count} normal={rainDaysExpected} />
      )}
    </Box>
  </>;
}

function TempMeanRow({ summary, normAvg }) {
  // Low/High = period extremes (no normal). Avg = mean of daily means with signed °
  // departure vs the mean of 1991-2020 daily normals over elapsed days.
  return <>
    <Box fontWeight="bold">Temperature</Box>
    <Box>{formatObs(unit, summary?.temp_min?.min_val, "temp")}</Box>
    <Box>{formatObs(unit, summary?.temp_max?.max_val, "temp")}</Box>
    <Box>
      {formatObs(unit, summary?.temp_avg?.avg, "temp")}
      <ClimateAnom inline value={summary?.temp_avg?.avg} normal={normAvg} obs="temp" stat="avg" unit={unit} />
    </Box>
  </>;
}

function MonthSummaryCard(props) {
  const summary = props.summary?.month;
  const date = serverDate(props.summary);
  const y = date?.[0], mo = date?.[1], d = date?.[2];
  const rainNormal = date ? periodToDateTotalNormal("rain", y, mo, 1, y, mo, d) : null;
  const sunNormal = date ? periodToDateTotalNormal("sun", y, mo, 1, y, mo, d) : null;
  const normAvg = date ? periodToDateTempNormal("avg", y, mo, 1, y, mo, d) : null;
  // No rain-day climate normal on site; omit expected-to-date anomaly.
  return <Box id="month-summary-card" width="460px" minHeight="250px" border="2px solid #656382" bg="gray.100" p={{ base: 2, md: 4 }} my={2} mx={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }}>This month averages &amp; extremes</Text>
    <Grid id="monthly-summary" key="monthly-summary"
      templateColumns="1.5fr repeat(3, 1fr)"
      templateRows="30px auto"
      rowGap="2"
      overflow="auto">
      <Box key="ms-base" id="ms-base"></Box>
      <Box fontWeight="bold">Low</Box>
      <Box fontWeight="bold">High</Box>
      <Box fontWeight="bold">Avg / total</Box>
      <TempMeanRow summary={summary} normAvg={normAvg} />
      <Box fontWeight="bold">Humidity</Box>
      <Box>{formatObs(unit, summary?.["humi_min"]?.["min_val"], "humi")}</Box>
      <Box>{formatObs(unit, summary?.["humi_max"]?.["max_val"], "humi")}</Box>
      <Box>{formatObs(unit, summary?.["humi_avg"]?.["avg"], "humi")}</Box>
      <Box fontWeight="bold">Dew point</Box>
      <Box>{formatObs(unit, summary?.["dewpt_min"]?.["min_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["dewpt_max"]?.["max_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["dewpt_avg"]?.["avg"], "temp")}</Box>
      <Box fontWeight="bold">Pressure</Box>
      <Box>{formatObs(unit, summary?.["pres_min"]?.["min_val"], "pres")}</Box>
      <Box>{formatObs(unit, summary?.["pres_max"]?.["max_val"], "pres")}</Box>
      <Box>{formatObs(unit, summary?.["pres_avg"]?.["avg"], "pres")}</Box>
      <Box fontWeight="bold">AQI (day avg)</Box>
      <Box>{formatObs(unit, summary?.["aqi_avg"]?.["min_val"], "aqi")}</Box>
      <Box>{formatObs(unit, summary?.["aqi_avg"]?.["max_val"], "aqi")}</Box>
      <Box>{formatObs(unit, summary?.["aqi_avg"]?.["avg"], "aqi")}</Box>
      <Box fontWeight="bold">Wind (day avg)</Box>
      <Box>{formatObs(unit, summary?.["wind_avg"]?.["min_val"], "wind")}</Box>
      <Box>{formatObs(unit, summary?.["wind_avg"]?.["max_val"], "wind")}</Box>
      <Box>{formatObs(unit, summary?.["wind_avg"]?.["avg"], "wind")}</Box>
      <PeriodRainSunRows summary={summary} rainNormal={rainNormal} sunNormal={sunNormal} />
    </Grid>
  </Box>
}


function YearSummaryCard(props) {
  const summary = props.summary?.year;
  const date = serverDate(props.summary);
  const y = date?.[0], mo = date?.[1], d = date?.[2];
  const rainNormal = date ? periodToDateTotalNormal("rain", y, 1, 1, y, mo, d) : null;
  const sunNormal = date ? periodToDateTotalNormal("sun", y, 1, 1, y, mo, d) : null;
  const normAvg = date ? periodToDateTempNormal("avg", y, 1, 1, y, mo, d) : null;
  return <Box id="year-summary-card" width="460px" minHeight="250px" border="2px solid #656382" bg="gray.100" p={{ base: 2, md: 4 }} m={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }}>This year averages &amp; extremes</Text>
    <Grid id="annual-summary" key="annual-summary"
      templateColumns="1.5fr repeat(3, 1fr)"
      templateRows="30px auto"
      rowGap="2"
      overflow="auto">
      <Box key="ms-base" id="ms-base"></Box>
      <Box fontWeight="bold">Low</Box>
      <Box fontWeight="bold">High</Box>
      <Box fontWeight="bold">Avg / total</Box>
      <TempMeanRow summary={summary} normAvg={normAvg} />
      <Box fontWeight="bold">Humidity</Box>
      <Box>{formatObs(unit, summary?.["humi_min"]?.["min_val"], "humi")}</Box>
      <Box>{formatObs(unit, summary?.["humi_max"]?.["max_val"], "humi")}</Box>
      <Box>{formatObs(unit, summary?.["humi_avg"]?.["avg"], "humi")}</Box>
      <Box fontWeight="bold">Dew point</Box>
      <Box>{formatObs(unit, summary?.["dewpt_min"]?.["min_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["dewpt_max"]?.["max_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["dewpt_avg"]?.["avg"], "temp")}</Box>
      <Box fontWeight="bold">Pressure</Box>
      <Box>{formatObs(unit, summary?.["pres_min"]?.["min_val"], "pres")}</Box>
      <Box>{formatObs(unit, summary?.["pres_max"]?.["max_val"], "pres")}</Box>
      <Box>{formatObs(unit, summary?.["pres_avg"]?.["avg"], "pres")}</Box>
      <Box fontWeight="bold">AQI (day avg)</Box>
      <Box>{formatObs(unit, summary?.["aqi_avg"]?.["min_val"], "aqi")}</Box>
      <Box>{formatObs(unit, summary?.["aqi_avg"]?.["max_val"], "aqi")}</Box>
      <Box>{formatObs(unit, summary?.["aqi_avg"]?.["avg"], "aqi")}</Box>
      <Box fontWeight="bold">Wind (day avg)</Box>
      <Box>{formatObs(unit, summary?.["wind_avg"]?.["min_val"], "wind")}</Box>
      <Box>{formatObs(unit, summary?.["wind_avg"]?.["max_val"], "wind")}</Box>
      <Box>{formatObs(unit, summary?.["wind_avg"]?.["avg"], "wind")}</Box>
      <PeriodRainSunRows summary={summary} rainNormal={rainNormal} sunNormal={sunNormal} />
    </Grid>
  </Box>
}


function RadioButtonGroup(props) {
  let { getRootProps, getRadioProps } = useRadioGroup({
    name: props.name,
    value: props.value,
    defaultValue: props.default,
    onChange: props.fn,
  })
  const group = getRootProps()
  return <Flex wrap="wrap" id={props.name} {...group} mb={1}>
    {props.options.map((value) => {
      const radio = getRadioProps({ value });
      let fs = props.ico ? { base: "xl", lg: "2xl" } : { base: "xs", sm: "sm", lg: "md" };
      return (
        <RadioCard key={value} px={{ base: 2, md: 3 }} py={{ base: 2, md: 2 }} box={{ fontSize: fs }} {...radio}>
          {props.optFormat(value)}
        </RadioCard>
      )
    })}
  </Flex>
}

// Memoized: no props from HomePage, so the ~3-9s live poll doesn't redraw this chart.
const ChartCardLatest = React.memo(function ChartCardLatest(props) {
  const obsOptions = ["temp", "rain", "humi", "dewpt", "aqi", "wind", "pres"];
  const hrsOptions = ["6", "12", "24", "72"];

  const [obs, setObs] = useState("temp");
  const [hrs, setHrs] = useState("6");
  // Wind plots speed and gust together (no direction on the home chart).
  const chartObs = obs;

  return <Box w={{ base: "98%", md: "80%", lg: "47%" }} border="2px solid #656382" bg="gray.100"
    p="2" my={2} mx={{ base: 0, md: 2, lg: 3, xl: 4 }} borderRadius="10px">
    <Flex wrap="wrap" justifyContent="space-between" alignItems="center">
      <RadioButtonGroup name="obs" value={obs} options={obsOptions} optFormat={fmatObsOptIcon} fn={setObs} ico={true} />
      <Box m={1}></Box>
      <RadioButtonGroup name="hrs" value={hrs} options={hrsOptions} optFormat={fmatTimeOpt} fn={setHrs} />
      <Box m={1}></Box>
      <Text><Link href="/charts/latest" title="More charts">More</Link></Text>
    </Flex>
    <LatestChart obs={chartObs} hrs={hrs} m={1} height="55%" spacing={[5, 5, 12, 3]} />
  </Box>
});

// Home 30-day wind: daily max or average, each showing speed and gust together.
const HOME_WIND_AGGS = ["max", "avg"];

// Memoized: no props from HomePage, so the ~3-9s live poll doesn't redraw this chart.
const ChartCardDaily = React.memo(function ChartCardDaily(props) {
  const obsOptions = ["temp", "rain", "sun", "humi", "dewpt", "aqi", "wind", "pres"];
  const aggOpts = ["avg", "max", "min"]

  const [obs, setObs] = useState("temp");
  const [aggType, setAggType] = useState("avg");
  const [sunView, setSunView] = useState("sun");  // sunshine as hours or % of possible (#24)
  const [rainView, setRainView] = useState("rain");  // rainfall as amount or wet hours
  const [windAgg, setWindAgg] = useState("max");  // wind: daily max or avg, speed and gust together
  const isSun = obs === "sun";
  const isRain = obs === "rain";
  const isWind = obs === "wind";
  const chartObs = isSun ? sunView : isRain ? rainView : isWind ? "wind" : obs;
  const chartAgg = isSun ? (sunView === "sunpct" ? "avg" : "total") : isRain ? OBS.get(rainView).summary : isWind ? windAgg : aggType;
  const period = "30";

  return <Box w={{ base: "98%", md: "80%", lg: "47%" }} border="2px solid #656382" bg="gray.100"
    p="2" my={2} mx={{ base: 0, md: 1, lg: 3, xl: 4 }} borderRadius="10px">
    <Flex wrap="wrap" justifyContent="space-between" alignItems="center">
      <RadioButtonGroup name="obs" value={obs} options={obsOptions} optFormat={fmatObsOptIcon} fn={setObs} ico={true} />
      <Box m={1}></Box>
      {isSun
        ? <RadioButtonGroup name="sunView" value={sunView} options={SUN_VIEWS} optFormat={(v) => SUN_VIEW_NAMES[v]} fn={setSunView} />
        : isRain
        ? <RadioButtonGroup name="rainView" value={rainView} options={RAIN_VIEWS} optFormat={(v) => RAIN_VIEW_NAMES[v]} fn={setRainView} />
        : isWind
        ? <RadioButtonGroup name="windAgg" value={windAgg} options={HOME_WIND_AGGS} optFormat={(v) => v} fn={setWindAgg} />
        : <RadioButtonGroup name="aggType" value={aggType} options={aggOpts} optFormat={(c) => c} fn={setAggType} />}
      <Box m={1}></Box>
      {/* <RadioButtonGroup name="period" options={periodOptions} optFormat={fmatDaysOpt} default={"30"} fn={setPeriod} /> */}
      <Text><Link href="/charts/summary" title="More charts">More</Link></Text>
    </Flex>
    <SummaryChart m={1} obs={chartObs} aggType={chartAgg} withGust={isWind} height="55%" chartType="column" period={period} spacing={[5, 5, 12, 3]} />
  </Box>
});


// Memoized: no props from HomePage, so the ~3-9s live poll doesn't redraw this chart.
const ChartCardYear = React.memo(function ChartCardYear(props) {
  // Same variable buttons as the home 30-day chart. Rain and sun (hours) are
  // always cumulative; everything else is daily. Reuses YearChart.
  const obsOptions = ["temp", "rain", "sun", "humi", "dewpt", "aqi", "wind", "pres"];
  const aggOpts = ["avg", "max", "min"];
  const CURRENT_YEAR = new Date().getFullYear();
  const [obs, setObs] = useState("temp");
  const [aggType, setAggType] = useState("avg");
  const [sunView, setSunView] = useState("sun");
  const [rainView, setRainView] = useState("rain");
  const [windView, setWindView] = useState("wind:max");
  const [today, setToday] = useState(null);
  useEffect(() => {
    const d = new Date();
    setToday([d.getFullYear(), d.getMonth() + 1, d.getDate()]);
  }, []);
  const isSun = obs === "sun";
  const isRain = obs === "rain";
  const isWind = obs === "wind";
  const [windObs, windAgg] = windView.split(":");
  const chartObs = isSun ? sunView : isRain ? rainView : isWind ? windObs : obs;
  const chartAgg = isSun ? (sunView === "sunpct" ? "avg" : "total")
    : isRain ? OBS.get(rainView).summary
    : isWind ? windAgg
    : aggType;
  // Only rainfall amount and sunshine hours are cumulative on the home year chart.
  const cumulative = chartObs === "rain" || chartObs === "sun";
  const moreHref = "/charts/year?var=" + chartObs
    + (chartAgg !== "avg" && chartAgg !== "total" ? "&daily=" + chartAgg : "")
    + (cumulative ? "&mode=cumulative" : "");

  return <Box id="home-year-chart-card" w={{ base: "98%", md: "96%", lg: "96%" }} border="2px solid #656382" bg="gray.100"
    p="2" my={2} mx={{ base: 0, md: 2, lg: 3, xl: 4 }} borderRadius="10px">
    <Flex wrap="wrap" justifyContent="space-between" alignItems="center">
      <RadioButtonGroup name="yearObs" value={obs} options={obsOptions} optFormat={fmatObsOptIcon} fn={setObs} ico={true} />
      <Box m={1}></Box>
      {isSun
        ? <RadioButtonGroup name="yearSunView" value={sunView} options={SUN_VIEWS} optFormat={(v) => SUN_VIEW_NAMES[v]} fn={setSunView} />
        : isRain
        ? <RadioButtonGroup name="yearRainView" value={rainView} options={RAIN_VIEWS} optFormat={(v) => RAIN_VIEW_NAMES[v]} fn={setRainView} />
        : isWind
        ? <RadioButtonGroup name="yearWindView" value={windView} options={WIND_SUMMARY_VIEWS} optFormat={(v) => WIND_SUMMARY_NAMES[v]} fn={setWindView} />
        : <RadioButtonGroup name="yearAggType" value={aggType} options={aggOpts} optFormat={(c) => c} fn={setAggType} />}
      <Box m={1}></Box>
      <Text><Link href={moreHref} title="More year charts">More</Link></Text>
    </Flex>
    <Box m={1}>
      <YearChart obs={chartObs} stat={chartAgg} year={CURRENT_YEAR} waterYear={false}
        cumulative={cumulative} showNormal={true} today={today}
        spacing={[5, 5, 12, 3]} />
    </Box>
  </Box>
});

// Webcam: preload each new frame off-screen and only swap it in once it has fully loaded (a failed or
// half-uploaded frame keeps the previous one). The box reserves the image's aspect ratio, so a refresh can
// never collapse the img and shrink the page (which yanked a reader scrolled to the bottom back up).
const CAM_URL = "https://rwcweather.com/cumulus/skycam_large.jpg";
const WebcamMemo = React.memo(function Webcam(props) {
  const [src, setSrc] = useState(CAM_URL + "?" + new Date().getTime());

  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  // every 6 s while visible, and at once when the page is viewed again
  useLivePoll("webcam", () => {
    const next = CAM_URL + "?" + new Date().getTime();
    const img = new window.Image();
    img.onload = () => { if (mounted.current && img.naturalWidth > 0) setSrc(next); };
    img.src = next;
  }, 6000);

  return <Box mt={2}>
    <Box m="auto" width={{ base: "95%", md: "720px", lg: "1200px", xl: "1500px" }}
      style={{ aspectRatio: "1560 / 878" }} overflow="hidden">
      <img id="cam" src={src} width="1560" height="878" alt="rwc weather cam"
        style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }} />
    </Box>
    <Text>Weather cam looking SE over the Emerald Hills canyon towards the southern SF peninsula.</Text>
  </Box>
});

function HomePage(props) {
  const data = useDashboard(props);
  const summary = useSummary();
  unit = useContext(UnitCtx);

  return <>
    <Heading as="h1" size="1">
      Live Weather for Redwood City, CA
    </Heading>
    <Flex
      justify="space-between"
      align={{ base: "flex-start", md: "center" }}
      direction={{ base: "column", md: "row" }}
      gap={{ base: 1, md: 4 }}
      pb="2"
      px={{ base: 1, sm: 2, md: 4, lg: 5 }}
    >
      <Box mx={2}>
        <LiveTime dash={data} />
      </Box>
      <Box mx={2}>
        <LiveDate dash={data} />
      </Box>
    </Flex>
    <Flex justify="center" wrap="wrap">
      <TemperatureHomeCard dash={data} summary={summary} />
      <WindHomeCard dash={data} summary={summary} />
      <RainHomeCard dash={data} summary={summary} />
      <HumidityHomeCard dash={data} summary={summary} />
      <PressureHomeCard dash={data} summary={summary} />
      <DewPtHomeCard dash={data} summary={summary} />
      <AirQualityHomeCard dash={data} summary={summary} />
      <SunshineHomeCard dash={data} summary={summary} />
      <AstronomyHomeCard dash={summary} summary={summary} />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <ChartCardLatest />
      <ChartCardDaily />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <ChartCardYear />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <RecapCard />
      <DayClimateExtremesCard dash={data} summary={summary} />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <MonthSummaryCard summary={summary} />
      <YearSummaryCard summary={summary} />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <AboutHomeCard />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <WebcamMemo />
    </Flex>
  </>;
}

export default function Home() {
  // This pattern allows context from Page to be extracted at a single level
  return <Page name="home" title="Dashboard"><HomePage live={{}} /></Page>;
}
