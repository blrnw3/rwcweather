import { Box, Flex, Heading, Text, useRadioGroup } from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { baseObs, dailyStatsFor, defaultDailyStat, fmatAggTypeOpt, fmatObsOpt, isTotalObs } from "../../components/conf";
import { Page } from "../../components/Page";
import RadioCard from "../../components/RadioCard";
import { hasWaterYears } from "../../components/waterYear";
import { REPORT_YEAR_START, SunViewToggle } from "../../components/report";
import { inList, useUrlState } from "../../components/urlState";
import { hasNormal, YearChart } from "../../components/yearChart";
import { ClimateNormalsLink } from "../../components/climate";

function RadioButtonGroup(props) {
  const { getRootProps, getRadioProps } = useRadioGroup({ name: props.name, value: props.value, onChange: props.fn });
  return <Flex wrap="wrap" py="1" id={props.name} {...getRootProps()}>
    {props.options.map((value) => (
      <RadioCard key={value.toString()} box={{ fontSize: { base: "sm", md: "md" } }} {...getRadioProps({ value })}>
        {props.optFormat(value)}
      </RadioCard>
    ))}
  </Flex>;
}

const obsOptions = ["temp", "rain", "sun", "dewpt", "humi", "wind", "pres"];
const CURRENT_YEAR = new Date().getFullYear();
const years = (water) => {
  const ys = [];
  for (let y = CURRENT_YEAR + (water ? 1 : 0); y >= REPORT_YEAR_START + (water ? 1 : 0); y--) ys.push(String(y));
  return ys;
};
const canCume = (obs) => isTotalObs(obs);

// e.g. /charts/year?var=rain&period=water&year=2026 ; /charts/year?var=temp&daily=min&year=2024
const YEAR_URL_STATE = {
  obs: { param: "var", def: () => "temp", valid: inList([...obsOptions, "sunpct", "wet", "wetrate"]) },
  stat: { param: "daily", def: (s) => defaultDailyStat(s.obs), valid: (v, s) => dailyStatsFor(s.obs).includes(v) },
  period: { param: "period", def: () => "calendar", valid: (v, s) => v === "calendar" || (v === "water" && hasWaterYears(s.obs)), use: (s) => hasWaterYears(s.obs) },
  year: { param: "year", def: (s) => years(s.period === "water")[0], valid: (v, s) => years(s.period === "water").includes(v) },
  cume: { param: "mode", def: (s) => (canCume(s.obs) ? "cumulative" : "daily"), valid: (v, s) => v === "daily" || (v === "cumulative" && canCume(s.obs)) },
  normal: { param: "normal", def: () => "on", valid: inList(["on", "off"]) },
};

const PERIOD_NAMES = { calendar: "Calendar year", water: "Water year (Oct–Sep)" };

export default function YearCharts() {
  const [{ obs, stat, period, year, cume, normal }, update] = useUrlState(YEAR_URL_STATE);
  const water = period === "water";
  const [today, setToday] = useState(null);
  useEffect(() => { const d = new Date(); setToday([d.getFullYear(), d.getMonth() + 1, d.getDate()]); }, []);

  const handleObsChange = (x) => update({
    obs: x, stat: defaultDailyStat(x, stat),
    cume: canCume(x) ? (canCume(obs) ? cume : "cumulative") : "daily",
    period: hasWaterYears(x) ? period : "calendar",
    year: hasWaterYears(x) || !water ? year : String(Math.min(Number(year), CURRENT_YEAR)),
  });
  const handlePeriod = (p) => {
    const ys = years(p === "water");
    update({ period: p, year: ys.includes(year) ? year : ys[0] });
  };

  return (
    <Page name="charts" sub="year" title="Charts | year">
      <Heading as="h1" size="1" mt="0">Year Charts</Heading>
      <Text mb="2">Every day of a year against the daily climate normal. Rainfall and sunshine can be shown as running totals.</Text>

      <Text mt="1" fontWeight="bold">Variable:</Text>
      <RadioButtonGroup name="obs" value={baseObs(obs)} options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
      <SunViewToggle obs={obs} fn={handleObsChange} Group={RadioButtonGroup} />
      {dailyStatsFor(obs).length > 1 && <>
        <Text mt="1" fontWeight="bold">Daily value:</Text>
        <RadioButtonGroup name="stat" value={stat} options={dailyStatsFor(obs)} optFormat={fmatAggTypeOpt} fn={(v) => update({ stat: v })} />
      </>}
      {hasWaterYears(obs) && <RadioButtonGroup name="period" value={period} options={["calendar", "water"]} optFormat={(p) => PERIOD_NAMES[p]} fn={handlePeriod} />}
      <Text mt="1" fontWeight="bold">{water ? "Water year (ending):" : "Year:"}</Text>
      <RadioButtonGroup name="year" value={year} options={years(water)} optFormat={(y) => (water ? "WY" + y : y)} fn={(v) => update({ year: v })} />
      <Flex wrap="wrap" gap="4">
        {canCume(obs) && <RadioButtonGroup name="mode" value={cume} options={["cumulative", "daily"]} optFormat={(v) => (v === "cumulative" ? "Cumulative" : "Daily")} fn={(v) => update({ cume: v })} />}
        {hasNormal(obs, stat) && <RadioButtonGroup name="normal" value={normal} options={["on", "off"]} optFormat={(v) => (v === "on" ? "Show normal" : "Hide normal")} fn={(v) => update({ normal: v })} />}
      </Flex>

      <Box my={4} mx={{ base: 0, md: 4, xl: 6 }}>
        <YearChart obs={obs} stat={stat} year={Number(year)} waterYear={water} cumulative={cume === "cumulative"}
          showNormal={normal === "on"} today={today} />
      </Box>
      {hasNormal(obs, stat)
        ? <><Text fontSize="sm">Daily normals are interpolated from the monthly normals (rainfall is spread evenly over each month's days; sunshine is smoothed between mid-months).</Text><ClimateNormalsLink mt="1" /></>
        : <Text fontSize="sm">There is no climate normal for {fmatObsOpt(obs).toLowerCase()}.</Text>}
    </Page>
  );
}
