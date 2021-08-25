import {
  Box,
  Flex, Grid, Heading, Link, Spinner, Text,
  Tooltip,
  useRadioGroup, Image
} from '@chakra-ui/react';
import { useContext, useEffect, useState } from 'react';
import { IconContext } from "react-icons";
import { GiDew } from "react-icons/gi";
import { FiWind } from "react-icons/fi";
import { ImArrowDown, ImArrowUp } from "react-icons/im";
import { IoTelescopeOutline } from "react-icons/io5";
import { RiHazeLine } from "react-icons/ri";
import { VscCircleFilled, VscDash } from "react-icons/vsc";
import { WiBarometer, WiHumidity, WiRain, WiThermometer } from "react-icons/wi";
import useSWR from "swr";
import { LatestChart, SummaryChart } from '../components/chart';
import { fetcher, fmatObsOptIcon, fmatTimeOpt } from '../components/conf';
import { Page, UnitCtx } from "../components/Page";
import RadioCard from '../components/RadioCard';
import { aqiStatus, formatObs, moonPhase, prettySecs, timeOf } from '../format';
import React from 'react';

let isLoading = true;
let errCount = 0;
let goodData;
let lastObs;
let unit;
let updateCount = 0;

function useDashboard(props) {
  let updateInterval = updateCount < 10 ? 3000 : 9000;
  const { data, error, isValidating } = useSWR(`/api/web/dashboard/live`, fetcher, { refreshInterval: updateInterval });
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
  const { data, error } = useSWR(`/api/web/dashboard/summary`, fetcher, { refreshInterval: 300000 })
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

  let icon = isLoading ? <Spinner mr="3" size="sm" speed="1s" color={status} /> : <IconContext.Provider value={{ color: status, size: "1.6em", style: { display: "inline" } }} >
    <VscCircleFilled /></IconContext.Provider>
  return <Text as="div" display="inline-block">
    <Box width="30px" height="30px" display="inline-block">{icon}</Box> {t}
  </Text>;
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

function LoHiCardSection(props) {
  let lo = formatObs(unit, props.hilo?.["min_val"], props.obs);
  let loAt = timeOf(props.hilo?.["min_at"]);
  let hi = formatObs(unit, props.hilo?.["max_val"], props.obs);
  let hiAt = timeOf(props.hilo?.["max_at"]);

  return <Box borderBottom="1px solid #ccc" borderTop="1px solid #ccc" py="1px">
    <Text>Lo: <Text as="span" fontWeight="bold">{lo}</Text> @ {loAt}</Text>
    <Text>Hi: <Text as="span" fontWeight="bold">{hi}</Text> @ {hiAt}</Text>
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
    <LoHiCardSection hilo={dash?.today?.temperature} obs="temp" />
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
  let monthly = formatObs(unit, props.summary?.["month"]?.["rain_total"]?.["total"], "rain");
  let annual = formatObs(unit, props.summary?.["year"]?.["rain_total"]?.["total"], "rain");
  let last = dash ? prettySecs(new Date(dash["now"]["t"]) - new Date(dash["last_rain"])) : "-";

  const icon = <Text as="span" color="blue" className="home_ico"><WiRain /></Text>
  return <HomeCard changed={changed}>
    <Text>
      <Tooltip label="Rainfall">{icon}</Tooltip>
      <Text as="span" fontSize={{ base: "2xl", md: "3xl" }} paddingRight="4" paddingLeft="1">{now}</Text>
    </Text>
    <Text borderBottom="1px solid #ccc">Last rain: <Text as="span" fontWeight="bold">{last}</Text> ago</Text>
    <Text>Monthly: <Text as="span" fontWeight="bold">{monthly}</Text></Text>
    <Text>Annual: <Text as="span" fontWeight="bold">{annual}</Text></Text>
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
    <Text marginBottom="1" borderBottom="1px solid #ccc">
      Moon set: <Text as="span" fontWeight="bold">{timeOf(astro?.set)}</Text>
    </Text>
    <Text>
      Sun rise: <Text as="span" fontWeight="bold">{timeOf(astro?.sunrise)}</Text>
    </Text>
    <Text borderBottom="1px solid #ccc">
      Sun set: <Text as="span" fontWeight="bold">{timeOf(astro?.sunset)}</Text>
    </Text>
    <Text >
      Daylight: <Text as="span" fontWeight="bold">{astro?.daylight_fmt}</Text>
    </Text>
  </HomeCard>
}

function MonthSummaryCard(props) {
  const summary = props.summary?.month;
  return <Box width="460px" minHeight="250px" border="2px solid #656382" bg="gray.100" p={{ base: 2, md: 4 }} my={2} mx={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }}>This month averages &amp; extremes</Text>
    <Grid id="monthly-summary" key="monthly-summary"
      templateColumns="1.5fr repeat(3, 1fr)"
      templateRows="30px auto"
      rowGap="2"
      overflow="auto">
      <Box key="ms-base" id="ms-base"></Box>
      <Box fontWeight="bold">Low</Box>
      <Box fontWeight="bold">High</Box>
      <Box fontWeight="bold">Avg</Box>
      <Box fontWeight="bold">Temperature</Box>
      <Box>{formatObs(unit, summary?.["temp_min"]?.["min_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["temp_max"]?.["max_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["temp_avg"]?.["avg"], "temp")}</Box>
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
    </Grid>
  </Box>
}

function YearSummaryCard(props) {
  const summary = props.summary?.year;
  return <Box width="460px" minHeight="250px" border="2px solid #656382" bg="gray.100" p={{ base: 2, md: 4 }} m={{ base: 0, md: 3 }} borderRadius="10px">
    <Text fontSize={{ base: "lg", md: "xl" }}>This year averages &amp; extremes</Text>
    <Grid id="annual-summary" key="annual-summary"
      templateColumns="1.5fr repeat(3, 1fr)"
      templateRows="30px auto"
      rowGap="2"
      overflow="auto">
      <Box key="ms-base" id="ms-base"></Box>
      <Box fontWeight="bold">Low</Box>
      <Box fontWeight="bold">High</Box>
      <Box fontWeight="bold">Avg</Box>
      <Box fontWeight="bold">Temperature</Box>
      <Box>{formatObs(unit, summary?.["temp_min"]?.["min_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["temp_max"]?.["max_val"], "temp")}</Box>
      <Box>{formatObs(unit, summary?.["temp_avg"]?.["avg"], "temp")}</Box>
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
    </Grid>
  </Box>
}

function RadioButtonGroup(props) {
  let { getRootProps, getRadioProps } = useRadioGroup({
    name: props.name,
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

function ChartCardLatest(props) {
  const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "dewpt"];
  const hrsOptions = ["6", "12", "24", "72"];

  const [obs, setObs] = useState("temp");
  const [hrs, setHrs] = useState("6");

  return <Box w={{ base: "98%", md: "80%", lg: "47%" }} border="2px solid #656382" bg="gray.100"
    p="2" my={2} mx={{ base: 0, md: 2, lg: 3, xl: 4 }} borderRadius="10px">
    <Flex wrap="wrap" justifyContent="space-between" alignItems="center">
      <RadioButtonGroup name="obs" options={obsOptions} optFormat={fmatObsOptIcon} default="temp" fn={setObs} ico={true} />
      <Box m={1}></Box>
      <RadioButtonGroup name="hrs" options={hrsOptions} optFormat={fmatTimeOpt} default={"6"} fn={setHrs} />
      <Box m={1}></Box>
      <Text><Link href="/charts/latest" title="More charts">More</Link></Text>
    </Flex>
    <LatestChart obs={obs} hrs={hrs} m={1} height="55%" spacing={[5, 5, 12, 3]} />
  </Box>
}

function ChartCardDaily(props) {
  const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "dewpt"];
  // const periodOptions = ["30", "60"];
  const aggOpts = ["avg", "max", "min"]

  const [obs, setObs] = useState("temp");
  const [aggType, setAggType] = useState("avg");
  // const [period, setPeriod] = useState("7")
  const period = "30";

  return <Box w={{ base: "98%", md: "80%", lg: "47%" }} border="2px solid #656382" bg="gray.100"
    p="2" my={2} mx={{ base: 0, md: 1, lg: 3, xl: 4 }} borderRadius="10px">
    <Flex wrap="wrap" justifyContent="space-between" alignItems="center">
      <RadioButtonGroup name="obs" options={obsOptions} optFormat={fmatObsOptIcon} default="temp" fn={setObs} ico={true} />
      <Box m={1}></Box>
      <RadioButtonGroup name="aggType" options={aggOpts} optFormat={(c) => c} default="avg" fn={setAggType} />
      <Box m={1}></Box>
      {/* <RadioButtonGroup name="period" options={periodOptions} optFormat={fmatDaysOpt} default={"30"} fn={setPeriod} /> */}
      <Text><Link href="/charts/summary" title="More charts">More</Link></Text>
    </Flex>
    <SummaryChart m={1} obs={obs} aggType={aggType} height="55%" chartType="column" period={period} spacing={[5, 5, 12, 3]} />
  </Box>
}

const WebcamMemo = React.memo(function Webcam(props) {
  const [ts, setTs] = useState(new Date().getTime());

  useEffect(() => {
    let interval = null;
    // NB: we pass a fn to setTs because this is a fire-once effect and so when the fn is setup, the value of ts keeps its initial val
    // see: https://stackoverflow.com/questions/54675523/state-inside-useeffect-refers-the-initial-state-always-with-react-hooks
    // and: https://stackoverflow.com/questions/62806541/how-to-solve-the-react-hook-closure-issue for how to get the latest state val in a closure
    interval = setInterval(() => {
      if(document.visibilityState != "hidden") {
        setTs((ts) => ts + 1);
      }
    }, 6000);
    return () => clearInterval(interval);
  }, []);

  return <Box mt={2}>
    <Box m="auto" width={{ base: "95%", md: "720px", lg: "1200px", xl: "1500px" }}
      height={{ base: "auto", md: "407px", lg: "675px", xl: "844px" }}>
      <img id="cam" src={"https://rwcweather.com/cumulus/skycam_large.jpg?" + ts} alt="rwc weather cam" />
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
    <Flex justify="space-between" pb="2" px={{ base: 1, sm: 2, md: 4, lg: 5 }}>
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
      <AstronomyHomeCard dash={summary} summary={summary} />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <ChartCardLatest />
      <ChartCardDaily />
    </Flex>
    <Flex justify="center" wrap="wrap">
      <MonthSummaryCard summary={summary} />
      <YearSummaryCard summary={summary} />
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
