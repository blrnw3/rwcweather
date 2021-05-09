import {
  Box,
  Flex,
  Heading,
  Text
} from '@chakra-ui/react';
import { IconContext } from "react-icons";
import { GiDew, GiLeafSwirl } from "react-icons/gi";
import { ImArrowDown, ImArrowUp } from "react-icons/im";
import { RiHazeLine } from "react-icons/ri";
import { VscArrowUp, VscCircleFilled, VscDash } from "react-icons/vsc";
import { WiBarometer, WiHumidity, WiRain, WiThermometer } from "react-icons/wi";
import useSWR from "swr";
import { Page } from "../components/Page";
import { formatObs, prettySecs, timeOf } from '../format';


const fetcher = url => fetch("http://localhost:5000" + url).then(res => res.json())
let lastObs;

function useDashboard () {
  const { data, error } = useSWR(`/web/dashboard`, fetcher, {refreshInterval: 5000})
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
  console.log(obsChange);
  lastObs = currObs;
  
  res["obs_change"] = obsChange;
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
    let diff = (t_server - t_dt) / 1000;
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
  return <Box width="300px" minHeight="200px" border={border} bg="gray.200" p="4" m="2" borderRadius="8px">
    {props.children}
  </Box>
}

function LoHiCardSection(props) {
  let lo = formatObs(props.hilo?.["min_val"], props.obs);
  let loAt = timeOf(props.hilo?.["min_at"]);
  let hi = formatObs(props.hilo?.["max_val"], props.obs);
  let hiAt = timeOf(props.hilo?.["max_at"]);

  return <Box>
      <Text>Lo: <Text as="span" fontWeight="bold">{lo}</Text> @ {loAt}</Text>
      <Text>Hi: <Text as="span" fontWeight="bold">{hi}</Text> @ {hiAt}</Text>
  </Box>
}

function TrendArrow(props) {
  let rawChange60 = (props.trends?.["0"]?.[props.obs] || 0) - (props.trends?.["60"]?.[props.obs] || 0)
  let change60 = formatObs(rawChange60, props.obs_conv, true);

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

function TemperatureHomeCard(props) {
  const dash = props.dash;
  const icon = <IconContext.Provider value={{ color: "red", size: "3em", style: {display: "inline"} }} ><WiThermometer /></IconContext.Provider>
  let temp = formatObs(dash?.["now"]?.["temp"], "temp");
  let changed = dash ? dash["obs_change"].get("temp") : null;

  return <HomeCard changed={changed}>
      <Text marginBottom="0.8em">
         {icon}
         <Text as="span" fontSize="3xl" paddingRight="4">{temp}</Text>
         <TrendArrow trends={dash?.trends} obs="temp" obs_conv="abs_temp" />
      </Text>
      <LoHiCardSection hilo={dash?.today?.temperature} obs="temp" />
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


  let changed = dash ? dash["obs_change"].get("wind") : null;

  return <HomeCard changed={changed}>
      <Text>
        <IconContext.Provider value={{ color: "brown", size: "2em", style: {display: "inline", paddingRight: "5px"} }} ><GiLeafSwirl /></IconContext.Provider>
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="2">{wind}</Text>
         <Text as="span" fontSize="2xl" paddingRight="1">{wdir}</Text>
      </Text>
      <Text marginBottom="0.8em">
        Gusting <Text as="span" fontSize="2xl">{gust}</Text>
      </Text>
      <Text>
        Max gust: <Text as="span" fontWeight="bold">{hi}</Text> @ {hiAt}
      </Text>
      <Text>
        Avg wind: <Text as="span" fontWeight="bold">{avgWind}</Text> {avgWdir}
      </Text>
  </HomeCard>
}

function RainHomeCard(props) {
  const dash = props.dash;
  let changed = dash ? dash["obs_change"].get("rain") : null;
  let now = formatObs(dash?.["now"]?.["rain"], "rain");
  let last = dash ? prettySecs(new Date(dash["now"]["t"]) - new Date(dash["last_rain"])) : "-"

  const icon = <IconContext.Provider value={{ color: "blue", size: "3em", style: {display: "inline"} }} ><WiRain /></IconContext.Provider>
  return <HomeCard changed={changed}>
      <Text>
          {icon}
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="1">{now}</Text>
      </Text>
      <Text>Last rain: <Text as="span" fontWeight="bold">{last}</Text> ago</Text>
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
         <Text as="span" fontSize="xl" paddingRight="2">{now}</Text>
         <TrendArrow trends={dash?.trends} obs="pres" obs_conv="pres" />
      </Text>
      <LoHiCardSection hilo={dash?.today?.pressure} obs="pres" />
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
  </HomeCard>
}

function AirQualityHomeCard(props) {
  const dash = props.dash;
  const icon = <IconContext.Provider value={{ color: "purple", size: "2em", style: {display: "inline"} }} ><RiHazeLine /></IconContext.Provider>
  let now = formatObs(dash?.["now"]?.["pm2"], "pm2");
  let changed = dash ? dash["obs_change"].get("pm2") : null;

  return <HomeCard changed={changed}>
      <Text marginBottom="0.8em">
         {icon}
         <Text as="span" fontSize="3xl" paddingRight="4" paddingLeft="2">{now}</Text>
         <TrendArrow trends={dash?.trends} obs="pm2" obs_conv="pm2" />
      </Text>
      <LoHiCardSection hilo={dash?.today?.pm2_5_level} obs="pm2" />
  </HomeCard>
}

function YesterdayHomeCard(props) {
  const dash = props.dash;
  return <HomeCard>
      <Text>
        <IconContext.Provider value={{ color: "orange", size: "2em", style: {display: "inline"} }} ><GiDew /></IconContext.Provider>
         <Text as="span" fontSize="3xl" paddingRight="4">? &deg;C</Text>
         <IconContext.Provider value={{ color: "green", size: "1em", style: {display: "inline"}  }} ><VscArrowUp /></IconContext.Provider>
           {" "}  +0.3 C /hr
      </Text>
      <Text>Dew Point</Text>
  </HomeCard>
}

function ForecastHomeCard(props) {
  return <HomeCard>
      <Text>
        <IconContext.Provider value={{ color: "orange", size: "2em", style: {display: "inline"} }} ><GiDew /></IconContext.Provider>
         <Text as="span" fontSize="3xl" paddingRight="4">? &deg;C</Text>
         <IconContext.Provider value={{ color: "green", size: "1em", style: {display: "inline"}  }} ><VscArrowUp /></IconContext.Provider>
           {" "}  +0.3 C /hr
      </Text>
      <Text>Dew Point</Text>
  </HomeCard>
}


export default function Home() {
  const data = useDashboard();

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
          <TemperatureHomeCard dash={data} />
          <WindHomeCard dash={data} />
          <RainHomeCard dash={data} />
          <HumidityHomeCard dash={data} />
          <PressureHomeCard dash={data} />
          <DewPtHomeCard dash={data} />
          <AirQualityHomeCard dash={data} />
        </Flex>
    </Page>
  )
}
