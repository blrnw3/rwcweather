import {
  Box,
  Flex,
  Heading,
  Grid,
  Text,
  Tooltip
} from '@chakra-ui/react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import { IconContext } from "react-icons";
import { GiDew, GiLeafSwirl } from "react-icons/gi";
import { ImArrowDown, ImArrowUp } from "react-icons/im";
import { RiHazeLine } from "react-icons/ri";
import { VscArrowUp, VscCircleFilled, VscDash } from "react-icons/vsc";
import { WiBarometer, WiHumidity, WiRain, WiThermometer, WiMoonAltWaningGibbous3, WiStars } from "react-icons/wi";
import { IoTelescopeOutline } from "react-icons/io5"
import useSWR from "swr";
import { fetcher, OBS } from '../components/conf';
import { Page } from "../components/Page";
import { aqiStatus, formatObs, moonPhase, prettySecs, timeOf, unitForObsType } from '../format';


let lastObs;

function useDashboard () {
  const { data, error } = useSWR(`/api/web/dashboard/live`, fetcher, {refreshInterval: 5000})
  if (error || !data) {
    console.log(error);
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
  return res;
}

function useSummary () {
  const { data, error } = useSWR(`/api/web/dashboard/summary`, fetcher, {refreshInterval: 300000})
  if (error || !data) {
    console.log(error);
    return error ? 0 : null;
  }
  let res = data["result"];
  res["server"] = data["server"];

  return res;
}

function useLatest (mins) {
  const { data, error } = useSWR("/api/obs/latest?d="+ mins, fetcher, {refreshInterval: 120000})
  if (error || !data) {
    console.log(error);
    return error ? 0 : null;
  }
  let res = data["result"];
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

  const dt_fmat = new Intl.DateTimeFormat("en-GB", {hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short"})
  let t = "Loading...";
  let status = "blue";
  if(dash === 0) {
    t = "Error getting data... retrying";
    status = "red";
  }
  if(dash) {
    let t_dt = new Date(dash["now"]["t_obs"]);
    let t_dt_fmt = dt_fmat.format(t_dt).replace("GMT-7", "PDT").replace("GMT-8", "PST");
    let t_server = new Date(dash["server"]["datetime"]);
    let diff = Math.round((t_server - t_dt) / 1000);
    if (diff > 100) {
      t = "Delayed ("+ diff +"s old): " + t_dt_fmt;
      status = "orange";
    } else {
      t = "Live ("+ diff +"s ago): " + t_dt_fmt;
      status = "#4b4";
    }
  }
  
  // setTimeout()

  return <Text>
      <IconContext.Provider value={{ color: status, size: "1.5em", style: {display: "inline"} }} ><VscCircleFilled /></IconContext.Provider> {t}
    </Text>;
}

function LiveDate(props) {
  const dash = props.dash;
  const dt_fmat = new Intl.DateTimeFormat("en-US", {day: "2-digit", month: "long", year:"numeric", weekday:"long"})
  let t = "Loading...";
  if(dash) {
    let t_dt = new Date(dash["now"]["t_obs"]);
    t = dt_fmat.format(t_dt);
  }
  return t;
}

function HomeCard(props) {
  let color = "#454332";
  if(props.changed != null) {
      color = props.changed ? "#459332" : "#954332";
  }
  let border = "1px solid " + color;
  return <Box minWidth="310px" border={border} bg="gray.200" p="4" m="2" borderRadius="8px">
    {props.children}
  </Box>
}

function LoHiCardSection(props) {
  let lo = formatObs(props.hilo?.["min_val"], props.obs);
  let loAt = timeOf(props.hilo?.["min_at"]);
  let hi = formatObs(props.hilo?.["max_val"], props.obs);
  let hiAt = timeOf(props.hilo?.["max_at"]);

  return <Box borderBottom="1px solid #ccc" borderTop="1px solid #ccc">
      <Text>Lo: <Text as="span" fontWeight="bold">{lo}</Text> @ {loAt}</Text>
      <Text>Hi: <Text as="span" fontWeight="bold">{hi}</Text> @ {hiAt}</Text>
  </Box>
}

function TrendArrow(props) {
  let rawChange60 = (props.trends?.["0"]?.[props.obs] || 0) - (props.trends?.["60"]?.[props.obs] || 0)
  let change60 = formatObs(rawChange60, props.obs_conv, true, false);

  let arrow = <VscDash />;
  let arrowColor = "blue";
  let arrowSize = "1em";
  if (rawChange60 != 0) {
    arrow = (rawChange60 > 0) ? <ImArrowUp /> : <ImArrowDown />;  // TODO: big vs small
    arrowColor = (rawChange60 > 0) ? "green" : "red";
  }
  return <Box as="span">
    <IconContext.Provider value={{ color: arrowColor, size: arrowSize, style: {display: "inline", paddingRight: "2"}  }}>{arrow}</IconContext.Provider>
           {change60} /hr
  </Box>
}
function TrendArrow24hr(props) {
  let rawChange = (props.trends?.["0"]?.[props.obs] || 0) - (props.trends?.["1440"]?.[props.obs] || 0)
  let change = formatObs(rawChange, props.obs_conv, true, false);

  let arrow = <VscDash />;
  let arrowColor = "blue";
  let arrowSize = "1em";
  if (rawChange != 0) {
    arrow = (rawChange > 0) ? <ImArrowUp /> : <ImArrowDown />;  // TODO: big vs small
    arrowColor = (rawChange > 0) ? "green" : "red";
  }
  return <Box as="span">
    Trend: <Text as="span" fontWeight="bold">{change}</Text> from 24hrs ago
    <IconContext.Provider value={{ color: arrowColor, size: arrowSize, style: {display: "inline", marginLeft: "5", paddingLeft: "2"}  }}>{arrow}</IconContext.Provider>
  </Box>
}

function YesterdayRange(props) {
  let yestLo = formatObs(props.summary?.["yesterday"]?.[props.name]["min_val"], props.fmat);
  let yestHi = formatObs(props.summary?.["yesterday"]?.[props.name]["max_val"], props.fmat);
  return <Text marginTop="1" >
    Yesterday: <Text as="span" fontWeight="bold">{yestLo}</Text> {"->"} <Text as="span" fontWeight="bold">{yestHi}</Text>
  </Text>
}

function TemperatureHomeCard(props) {
  const dash = props.dash;
  const icon = <IconContext.Provider value={{ color: "red", size: "3em", style: {display: "inline"} }} ><WiThermometer /></IconContext.Provider>
  let temp = formatObs(dash?.["now"]?.["temp"], "temp");
  let feels = formatObs(dash?.["now"]?.["feels"], "temp");
  let changed = dash ? dash["obs_change"].get("temp") : null;
  let feelsIco = dash?.["now"]?.["feels"] > dash?.["now"]?.["temp"] ? "🥵" : (dash?.["now"]?.["feels"] < dash?.["now"]?.["temp"] ? "🥶": "");

  return <HomeCard changed={changed}>
      <Text>
         {icon}
         <Text as="span" fontSize="3xl" paddingRight="4">{temp}</Text>
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
  const icon = <IconContext.Provider value={{ color: "green", size: "3em", style: {display: "inline"} }} ><WiHumidity /></IconContext.Provider>
  let now = formatObs(dash?.["now"]?.["humi"], "humi");
  let changed = dash ? dash["obs_change"].get("humi") : null;

  return <HomeCard changed={changed}>
      <Text marginBottom="0.8em">
         {icon}
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="1">{now}</Text>
         <TrendArrow trends={dash?.trends} obs="humi" obs_conv="humi" />
      </Text>
      <LoHiCardSection hilo={dash?.today?.humidity} obs="humi" />
      <YesterdayRange summary={props.summary} name="humidity" fmat="humi" />
      <TrendArrow24hr trends={dash?.trends} obs="humi" obs_conv="humi" />
  </HomeCard>
}

function WindHomeCard(props) {
  const dash = props.dash;
  let wind = formatObs(dash?.["now"]?.["wind"], "wind");
  let wdir = formatObs(dash?.["now"]?.["wdir"], "wdir");
  let gust = formatObs(dash?.["now"]?.["gust"], "gust");

  let hi = formatObs(dash?.today?.gust_speed?.["max_val"], "gust");
  let hiAt = timeOf(dash?.today?.gust_speed?.["max_at"]);

  let avgWind = formatObs(dash?.today?.wind_speed?.["avg"], "wind");
  let avgWdir = formatObs(dash?.today?.wind_direction?.["avg"], "wdir");
  let yestAvg = formatObs(props.summary?.["yesterday"]?.["wind_speed"]["avg"], "wind");

  let changed = dash ? dash["obs_change"].get("wind") : null;

  return <HomeCard changed={changed}>
      <Text>
        <IconContext.Provider value={{ color: "brown", size: "2em", style: {display: "inline", paddingRight: "5px"} }} ><GiLeafSwirl /></IconContext.Provider>
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="2">{wind}</Text>
         <Text as="span" fontSize="2xl" paddingRight="1">{wdir}</Text>
      </Text>
      <Text marginBottom="1" borderBottom="1px solid #ccc">
        Gusting <Text as="span" fontSize="2xl">{gust}</Text>
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
  let now = formatObs(dash?.["now"]?.["rain"], "rain");
  let monthly = formatObs(props.summary?.["month"]?.["rain_total"]?.["total"], "rain");
  let annual = formatObs(props.summary?.["year"]?.["rain_total"]?.["total"], "rain");
  let last = dash ? prettySecs(new Date(dash["now"]["t"]) - new Date(dash["last_rain"])) : "-";

  const icon = <IconContext.Provider value={{ color: "blue", size: "3em", style: {display: "inline"} }} ><WiRain /></IconContext.Provider>
  return <HomeCard changed={changed}>
      <Text>
          <Tooltip label="Rainfall">{icon}</Tooltip>
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="1">{now}</Text>
      </Text>
      <Text borderBottom="1px solid #ccc">Last rain: <Text as="span" fontWeight="bold">{last}</Text> ago</Text>
      <Text>Monthly: <Text as="span" fontWeight="bold">{monthly}</Text></Text>
      <Text>Annual: <Text as="span" fontWeight="bold">{annual}</Text></Text>
  </HomeCard>
}

function PressureHomeCard(props) {
  const dash = props.dash;
  const icon = <IconContext.Provider value={{ color: "gray", size: "2.5em", style: {display: "inline"} }} ><WiBarometer /></IconContext.Provider>
  let now = formatObs(dash?.["now"]?.["pres"], "pres");
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
  const icon = <IconContext.Provider value={{ color: "orange", size: "2em", style: {display: "inline"} }} ><GiDew /></IconContext.Provider>
  let now = formatObs(dash?.["now"]?.["dewpt"], "temp");
  let changed = dash ? dash["obs_change"].get("dewpt") : null;

  return <HomeCard changed={changed}>
      <Text marginBottom="0.8em">
         {icon}
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="2">{now}</Text>
         <TrendArrow trends={dash?.trends} obs="dewpt" obs_conv="abs_temp" />
      </Text>
      <LoHiCardSection hilo={dash?.today?.dew_point} obs="temp" />
      <YesterdayRange summary={props.summary} name="dew_point" fmat="temp" />
      <TrendArrow24hr trends={dash?.trends} obs="dewpt" obs_conv="abs_temp" />
  </HomeCard>
}

function AirQualityHomeCard(props) {
  const dash = props.dash;
  const icon = <IconContext.Provider value={{ color: "purple", size: "2em", style: {display: "inline"} }} ><RiHazeLine /></IconContext.Provider>
  let now = "AQI " + formatObs(dash?.["now"]?.["aqi"], "aqi");
  let pm2 = formatObs(dash?.["now"]?.["pm2"], "pm2");
  let avg = formatObs(dash?.["today"]?.["aqi"]?.["avg"], "aqi");
  let statusAvg = aqiStatus(dash?.["today"]?.["aqi"]?.["avg"]);
  let changed = dash ? dash["obs_change"].get("aqi") : null;
  let pm2Label = "PM 2.5: " + pm2;
  let yestAvg = formatObs(props.summary?.["yesterday"]?.["aqi"]?.["avg"], "aqi");
  // let yestAvgStatus = aqiStatus(props.summary?.["yesterday"]?.["aqi"]?.["avg"]);

  return <HomeCard changed={changed}>
      <Text marginBottom="0.8em">
         {icon}
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="2"><Tooltip label={pm2Label}>{now}</Tooltip></Text>
         <TrendArrow trends={dash?.trends} obs="aqi" obs_conv="aqi" />
      </Text>
      <Text>
        Avg: <Text as="span" fontWeight="bold" marginRight="2">{avg}</Text>
        <Tooltip label={statusAvg[1]}>{statusAvg[0]}</Tooltip>
      </Text>
      <LoHiCardSection hilo={dash?.today?.aqi} obs="aqi" />
      <Text marginTop="1">
        Yesterday Avg: <Text as="span" fontWeight="bold" marginRight="2">{yestAvg}</Text>
        {/* <Tooltip label={yestAvgStatus[1]}>{yestAvgStatus[0]}</Tooltip> */}
      </Text>
  </HomeCard>
}

function AstronomyHomeCard(props) {
  const astro = props.dash?.astronomy;
  let frac = formatObs(astro?.fraction * 100, "humi")
  const icon = <IconContext.Provider value={{ color: "black", size: "2.5em", style: {display: "inline"} }} ><IoTelescopeOutline /></IconContext.Provider>
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
  return <Box width="460px" minHeight="250px" border="2px solid #656382" bg="gray.100" p="4" m="3" borderRadius="10px">
      <Text fontSize="xl">Monthly avg &amp; extremes</Text>
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
        <Box>{formatObs(summary?.["temp_min"]["min_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["temp_max"]["max_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["temp_avg"]["avg"], "temp")}</Box>
        <Box fontWeight="bold">Humidity</Box>
        <Box>{formatObs(summary?.["humi_min"]["min_val"], "humi")}</Box>
        <Box>{formatObs(summary?.["humi_max"]["max_val"], "humi")}</Box>
        <Box>{formatObs(summary?.["humi_avg"]["avg"], "humi")}</Box>
        <Box fontWeight="bold">Dew point</Box>
        <Box>{formatObs(summary?.["dewpt_min"]["min_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["dewpt_max"]["max_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["dewpt_avg"]["avg"], "temp")}</Box>
        <Box fontWeight="bold">Pressure</Box>
        <Box>{formatObs(summary?.["pres_min"]["min_val"], "pres")}</Box>
        <Box>{formatObs(summary?.["pres_max"]["max_val"], "pres")}</Box>
        <Box>{formatObs(summary?.["pres_avg"]["avg"], "pres")}</Box>
        <Box fontWeight="bold">AQI (day avg)</Box>
        <Box>{formatObs(summary?.["aqi_avg"]["min_val"], "aqi")}</Box>
        <Box>{formatObs(summary?.["aqi_avg"]["max_val"], "aqi")}</Box>
        <Box>{formatObs(summary?.["aqi_avg"]["avg"], "aqi")}</Box>
        <Box fontWeight="bold">Wind (day avg)</Box>
        <Box>{formatObs(summary?.["wind_avg"]["min_val"], "wind")}</Box>
        <Box>{formatObs(summary?.["wind_avg"]["max_val"], "wind")}</Box>
        <Box>{formatObs(summary?.["wind_avg"]["avg"], "wind")}</Box>
      </Grid>
  </Box>
}

function YearSummaryCard(props) {
  const summary = props.summary?.year;
  return <Box width="460px" minHeight="250px" border="2px solid #656382" bg="gray.100" p="4" m="3" borderRadius="10px">
      <Text fontSize="xl">Annual avg &amp; extremes</Text>
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
        <Box>{formatObs(summary?.["temp_min"]["min_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["temp_max"]["max_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["temp_avg"]["avg"], "temp")}</Box>
        <Box fontWeight="bold">Humidity</Box>
        <Box>{formatObs(summary?.["humi_min"]["min_val"], "humi")}</Box>
        <Box>{formatObs(summary?.["humi_max"]["max_val"], "humi")}</Box>
        <Box>{formatObs(summary?.["humi_avg"]["avg"], "humi")}</Box>
        <Box fontWeight="bold">Dew point</Box>
        <Box>{formatObs(summary?.["dewpt_min"]["min_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["dewpt_max"]["max_val"], "temp")}</Box>
        <Box>{formatObs(summary?.["dewpt_avg"]["avg"], "temp")}</Box>
        <Box fontWeight="bold">Pressure</Box>
        <Box>{formatObs(summary?.["pres_min"]["min_val"], "pres")}</Box>
        <Box>{formatObs(summary?.["pres_max"]["max_val"], "pres")}</Box>
        <Box>{formatObs(summary?.["pres_avg"]["avg"], "pres")}</Box>
        <Box fontWeight="bold">AQI (day avg)</Box>
        <Box>{formatObs(summary?.["aqi_avg"]["min_val"], "aqi")}</Box>
        <Box>{formatObs(summary?.["aqi_avg"]["max_val"], "aqi")}</Box>
        <Box>{formatObs(summary?.["aqi_avg"]["avg"], "aqi")}</Box>
        <Box fontWeight="bold">Wind (day avg)</Box>
        <Box>{formatObs(summary?.["wind_avg"]["min_val"], "wind")}</Box>
        <Box>{formatObs(summary?.["wind_avg"]["max_val"], "wind")}</Box>
        <Box>{formatObs(summary?.["wind_avg"]["avg"], "wind")}</Box>
      </Grid>
  </Box>
}

function HomeChart(props) {
  let obs = props.obs;
  let obsName = OBS.get(obs).name;
  let unit = unitForObsType(OBS.get(obs).fmat);
  let hrs = props.hrs;
  let duration = (hrs < 50) ? hrs + " hrs" : Math.round(hrs / 24) + " days";
  const latest = useLatest(hrs * 60);
  let temp;
  if(!latest) {
      temp = [[0, 0]];
  } else {
      temp = latest.map(x => [x["t"], x[obs]]).reverse();
  }
  let options = {
      chart: {
        height: "48%",
        spacing: [20, 20, 25, 10]
      },
      legend: {
        enabled: false
      },
      credits: {
          href: null,
          text: "@rwcweather"
      },
      title: {
        text: "Last "+ duration + " " + obsName + " in Redwood City"
      },
      time: {
          timezoneOffset: 60 * 7  // TODO!
      },
      xAxis: {
          type: "datetime"
      },
      yAxis: {
        title: {
          text: obsName + " / " + unit
        }
      },
      series: [{
        data: temp,
        name: obs
      }]
    }
  return <Box m="4">
      <HighchartsReact
          highcharts={Highcharts}
          options={options}
      />
  </Box>
}

function ChartCard(props) {
  return <Box width="600px" minHeight="250px" border="2px solid #656382" bg="gray.100" p="4" m="3" borderRadius="10px">
      <HomeChart obs="temp" hrs="6" />
  </Box>
}


export default function Home() {
  const data = useDashboard();
  const summary = useSummary();

  return (
    <Page>
      <Heading>
        Latest Conditions in Redwood City, CA
      </Heading>
        <Flex justify="space-between" p="2">
          <Box>
            <LiveTime dash={data} />
          </Box>
          <Box>
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
          <MonthSummaryCard summary={summary} />
          <YearSummaryCard summary={summary} />
        </Flex>
        <ChartCard />
    </Page>
  )
}
