import { Box, Flex, Heading, Text, useRadioGroup } from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { baseObs, dailyStatsFor, defaultDailyStat, fmatAggTypeOpt, fmatObsOpt, isTotalObs } from "../../components/conf";
import { Page } from "../../components/Page";
import RadioCard from "../../components/RadioCard";
import { hasWaterYears } from "../../components/waterYear";
import { DAILY_VALUE_OBS_OPTIONS, DAILY_VALUE_OBS_STATES, DerivedVarNote, REPORT_YEAR_START, SunViewToggle } from "../../components/report";
import { inList, useUrlState } from "../../components/urlState";
import { hasDayStats, hasNormal, isMobile, STATS_MODES, YearChart } from "../../components/yearChart";
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

const obsOptions = DAILY_VALUE_OBS_OPTIONS;
const CURRENT_YEAR = new Date().getFullYear();
const years = (water) => {
  const ys = [];
  for (let y = CURRENT_YEAR + (water ? 1 : 0); y >= REPORT_YEAR_START + (water ? 1 : 0); y--) ys.push(String(y));
  return ys;
};
const canCume = (obs) => isTotalObs(obs);

// "all" = no single year: just the all-years average / lowest / highest for each calendar day
const yearOptions = (water, obs) => (hasDayStats(obs) ? ["all"] : []).concat(years(water));

// e.g. /charts/year?var=rain&period=water&year=2026 ; /charts/year?var=temp&daily=min&year=2024
//      /charts/year?var=temp&daily=max&year=2025&stats=on ; /charts/year?var=rain&year=all
const YEAR_URL_STATE = {
  obs: { param: "var", def: () => "temp", valid: inList(DAILY_VALUE_OBS_STATES) },
  stat: { param: "daily", def: (s) => defaultDailyStat(s.obs), valid: (v, s) => dailyStatsFor(s.obs).includes(v) },
  period: { param: "period", def: () => "calendar", valid: (v, s) => v === "calendar" || (v === "water" && hasWaterYears(s.obs)), use: (s) => hasWaterYears(s.obs) },
  year: { param: "year", def: (s) => years(s.period === "water")[0], valid: (v, s) => yearOptions(s.period === "water", s.obs).includes(v) },
  cume: { param: "mode", def: (s) => (canCume(s.obs) ? "cumulative" : "daily"), valid: (v, s) => v === "daily" || (v === "cumulative" && canCume(s.obs)) },
  normal: { param: "normal", def: () => "on", valid: inList(["on", "off"]), use: (s) => s.year !== "all" },
  // all-years overlay: off | avg (average only) | range (average + lowest-highest band). year=all has no "off" and
  // defaults to range. Links from before the 3-way choice used stats=on, which means range.
  stats: {
    param: "stats", fromUrl: (v) => (v === "on" ? "range" : v),
    def: (s) => (s.year === "all" ? "range" : "off"),
    valid: (v, s) => (s.year === "all" ? ["avg", "range"] : STATS_MODES).includes(v),
    use: (s) => hasDayStats(s.obs),
  },
};

const STATS_NAMES = { off: "Off", avg: "Average", range: "Avg + range" };
// Taller than the homepage's chart (460 / 360): 1.5x on desktop, and enough on a phone for the band to read.
const chartHeight = () => (isMobile() ? 440 : 690);

const PERIOD_NAMES = { calendar: "Calendar year", water: "Water year (Oct–Sep)" };

export default function YearCharts() {
  const [{ obs, stat, period, year, cume, normal, stats }, update] = useUrlState(YEAR_URL_STATE);
  const water = period === "water";
  const all = year === "all";
  const [today, setToday] = useState(null);
  useEffect(() => { const d = new Date(); setToday([d.getFullYear(), d.getMonth() + 1, d.getDate()]); }, []);

  const handleObsChange = (x, nextStat) => update({
    obs: x,
    stat: nextStat || (x === "wind" ? "max" : defaultDailyStat(x, stat)),
    cume: canCume(x) ? (canCume(obs) ? cume : "cumulative") : "daily",
    period: hasWaterYears(x) ? period : "calendar",
    year: year === "all" ? (hasDayStats(x) ? "all" : years(false)[0])
      : hasWaterYears(x) || !water ? year : String(Math.min(Number(year), CURRENT_YEAR)),
  });
  const handlePeriod = (p) => {
    const ys = years(p === "water");
    update({ period: p, year: year === "all" || ys.includes(year) ? year : ys[0] });
  };

  return (
    <Page name="charts" sub="year" title="Charts | year">
      <Heading as="h1" size="1" mt="0">Year Charts</Heading>
      <Text mb="2">Every day of a year against the daily climate normal, and against the all-years average (optionally with the lowest and highest) for that day. Rainfall and sunshine can be shown as running totals.</Text>

      <Text mt="1" fontWeight="bold">Variable:</Text>
      <RadioButtonGroup name="obs" value={baseObs(obs)} options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
      <SunViewToggle obs={obs} stat={stat} fn={handleObsChange} Group={RadioButtonGroup} />
      {baseObs(obs) !== "wind" && dailyStatsFor(obs).length > 1 && <>
        <Text mt="1" fontWeight="bold">Daily value:</Text>
        <RadioButtonGroup name="stat" value={stat} options={dailyStatsFor(obs)} optFormat={fmatAggTypeOpt} fn={(v) => update({ stat: v })} />
      </>}
      {hasWaterYears(obs) && <RadioButtonGroup name="period" value={period} options={["calendar", "water"]} optFormat={(p) => PERIOD_NAMES[p]} fn={handlePeriod} />}
      <Text mt="1" fontWeight="bold">{water ? "Water year (ending):" : "Year:"}</Text>
      <RadioButtonGroup name="year" value={year} options={yearOptions(water, obs)} optFormat={(y) => (y === "all" ? "All" : water ? "WY" + y : y)} fn={(v) => update({ year: v })} />
      <Flex wrap="wrap" gap="4">
        {canCume(obs) && <RadioButtonGroup name="mode" value={cume} options={["cumulative", "daily"]} optFormat={(v) => (v === "cumulative" ? "Cumulative" : "Daily")} fn={(v) => update({ cume: v })} />}
        {hasDayStats(obs) && <Flex align="center" wrap="wrap">
          <Text fontWeight="bold" mr="2">All years:</Text>
          <RadioButtonGroup name="stats" value={stats} options={all ? ["avg", "range"] : STATS_MODES} optFormat={(v) => STATS_NAMES[v]} fn={(v) => update({ stats: v })} />
        </Flex>}
        {!all && hasNormal(obs, stat) && <RadioButtonGroup name="normal" value={normal} options={["on", "off"]} optFormat={(v) => (v === "on" ? "Show normal" : "Hide normal")} fn={(v) => update({ normal: v })} />}
      </Flex>

      <Box my={4} mx={{ base: 0, md: 4, xl: 6 }}>
        <YearChart obs={obs} stat={stat} year={all ? null : Number(year)} waterYear={water} cumulative={cume === "cumulative"}
          showNormal={normal === "on"} stats={stats} allYears={all} today={today} height={chartHeight()} />
      </Box>
      {hasDayStats(obs) && stats !== "off" && <Text fontSize="sm" mb="1">
        {cume === "cumulative"
          ? "All years: the " + (stats === "range" ? "average, lowest and highest " : "average ") + "running total reached by each date, over every complete " + (water ? "water" : "calendar") + " year in the record (from Dec 2020; sunshine from Sep 2021), plus the current one so far."
          : "All years: the " + (stats === "range" ? "average, lowest and highest " : "average ") + (isTotalObs(obs) ? "daily total" : dailyStatsFor(obs).length < 2 ? "daily value" : "daily " + fmatAggTypeOpt(stat).toLowerCase()) + " recorded on each calendar day since records began (Dec 2020; sunshine Sep 2021), excluding today. 29 February pools 28 Feb–1 Mar."}
      </Text>}
      {all ? null : hasNormal(obs, stat)
        ? <><Text fontSize="sm">Daily normals are interpolated from the monthly normals (rainfall is spread evenly over each month's days; sunshine is smoothed between mid-months).</Text><ClimateNormalsLink mt="1" /></>
        : <Text fontSize="sm">There is no climate normal for {fmatObsOpt(obs).toLowerCase().replace("et0", "ET0")}.</Text>}
      <DerivedVarNote obs={obs} mt="2" />
    </Page>
  );
}
