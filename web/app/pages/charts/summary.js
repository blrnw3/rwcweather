import { Flex, Heading, Text, useRadioGroup } from "@chakra-ui/react";
import { SummaryChart } from "../../components/chart";
import { baseObs, fmatAggTypeOpt, fmatDaysOpt, fmatObsOpt, fmatOptCapitalize, isTotalObs, OBS } from '../../components/conf';
import { DAILY_VALUE_OBS_OPTIONS, DAILY_VALUE_OBS_STATES, SunViewToggle } from '../../components/report';
import { Page } from "../../components/Page";
import { inList, useUrlState } from "../../components/urlState";
import RadioCard from '../../components/RadioCard';


function RadioButtonGroup(props) {
  let { getRootProps, getRadioProps } = useRadioGroup({
    name: props.name,
    value: props.value,
    onChange: props.fn,
  })
  const group = getRootProps()
  return <Flex wrap="wrap" py="1" id={props.name} {...group}>
    {props.options.map((value) => {
      const radio = getRadioProps({ value });
      return (
        <RadioCard key={value.toString()} box={{fontSize: {base: "sm", md: "md"}}} {...radio}>
          {props.optFormat(value)}
        </RadioCard>
      )
    })}
  </Flex>
}

const obsOptions = DAILY_VALUE_OBS_OPTIONS;
const periodOpts = ["30", "90", "180", "365"];
const aggOptionsFor = (obs) => isTotalObs(obs) ? ["total"] : (OBS.get(obs).dailyStats || ["max", "min", "avg"]);
const yrStart = 2020;
const yrEnd = new Date().getFullYear();
const yearOpts = ["recent", ...Array.from(Array(yrEnd - yrStart + 1).keys()).map((i) => String(yrEnd - i))];
const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const monthOpts = ["all", ...Array.from(Array(12).keys()).map((m) => String(m + 1))];
const monthParam = (value) => value === "all" ? "all" : monthNames[Number(value) - 1].toLowerCase();
const monthFromParam = (value) => {
  const index = monthNames.findIndex((name) => name.toLowerCase() === String(value).toLowerCase());
  return index >= 0 ? String(index + 1) : value;
};

// Selections kept in the URL, e.g. /charts/summary?var=rain&days=365&chart=line
const SUMMARY_URL_STATE = {
  obs: { param: "var", def: () => "temp", valid: inList(DAILY_VALUE_OBS_STATES) },
  aggType: { param: "daily", def: (s) => aggOptionsFor(s.obs)[0], valid: (v, s) => aggOptionsFor(s.obs).includes(v) },
  period: { param: "days", def: () => "30", valid: inList(periodOpts), use: (s) => s.year === "recent" },
  year: { def: () => "recent", valid: inList(yearOpts) },
  month: { def: () => "all", valid: inList(monthOpts), toUrl: monthParam, fromUrl: monthFromParam, use: (s) => s.year !== "recent" },
  chartType: { param: "chart", def: () => "column", valid: inList(["column", "line"]) },
};

export default function Charts() {
  const [{ obs, aggType, period, year, month, chartType }, update] = useUrlState(SUMMARY_URL_STATE);
  const aggOpts = aggOptionsFor(obs);

  // Rain only has daily totals; other variables keep their statistic.
  const handleObsChange = (x, nextAgg) => update({
    obs: x,
    aggType: nextAgg || (x === "wind" ? "max" : aggOptionsFor(x).includes(aggType) ? aggType : aggOptionsFor(x)[0]),
  });
  const setAggType = (value) => update({ aggType: value });
  const setPeriod = (value) => update({ year: "recent", month: "all", period: value });
  const setYear = (value) => update({ year: value, ...(value === "recent" ? { month: "all" } : {}) });
  const setMonth = (value) => {
    if (year === "recent" && value !== "all") {
      const now = new Date();
      const targetYear = Number(value) > now.getMonth() + 1 ? now.getFullYear() - 1 : now.getFullYear();
      update({ year: String(targetYear), month: value });
    } else {
      update({ month: value });
    }
  };
  const setChartType = (value) => update({ chartType: value });

  const periodDesc = year !== "recent"
    ? ("in " + (month !== "all" ? monthNames[Number(month) - 1] + " " : "") + year)
    : ("in the past " + period + " days");

  return (
    <Page name="charts" sub="summary" title="Charts | summary">
      <Heading as="h1" size="1" mt="0">
        Summary Charts
      </Heading>

      <Heading size="2" as="h2">
        Daily {fmatAggTypeOpt(aggType)} {OBS.get(obs).name} {periodDesc}
      </Heading>

      <RadioButtonGroup name="obs" value={baseObs(obs)} options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
      <SunViewToggle obs={obs} stat={aggType} fn={handleObsChange} Group={RadioButtonGroup} />
      {baseObs(obs) !== "wind" && aggOpts.length > 1 && <RadioButtonGroup name="agg" value={aggType} options={aggOpts} optFormat={fmatAggTypeOpt} fn={setAggType} />}

      <SummaryChart obs={obs} aggType={aggType} chartType={chartType} period={period} year={year} month={month} my={4} mx={{base: 0, md: 4, xl: 6}}
       height="responsive" spacing={[20, 20, 25, 10]} />

      <Text mt="1" fontWeight="bold">Recent days:</Text>
      <RadioButtonGroup name="period" value={year === "recent" ? period : ""} options={periodOpts} optFormat={fmatDaysOpt} fn={setPeriod} />
      <Text mt="1" fontWeight="bold">Year:</Text>
      <RadioButtonGroup name="year" value={year} options={yearOpts} optFormat={(y) => y === "recent" ? "Recent" : y} fn={setYear} />
      <Text mt="1" fontWeight="bold">Month:</Text>
      <RadioButtonGroup name="month" value={year === "recent" ? "all" : month} options={monthOpts} optFormat={(m) => m === "all" ? "All months" : monthNames[Number(m) - 1]} fn={setMonth} />
      <Text mt="1" fontWeight="bold">Chart type:</Text>
      <RadioButtonGroup name="chart-type" value={chartType} options={["column", "line"]} optFormat={fmatOptCapitalize} fn={setChartType} />

    </Page>
  )
}
