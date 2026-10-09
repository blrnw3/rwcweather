import { Flex, Heading, useRadioGroup } from "@chakra-ui/react";
import { SummaryChart } from "../../components/chart";
import { fmatAggTypeOpt, fmatDaysOpt, fmatObsOpt, fmatOptCapitalize, OBS } from '../../components/conf';
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

const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt"];
const periodOpts = ["30", "90", "180", "365"];
const aggOptionsFor = (obs) => obs === "rain" ? ["total"] : ["max", "min", "avg"];

// Selections kept in the URL, e.g. /charts/summary?var=rain&days=365&chart=line
const SUMMARY_URL_STATE = {
  obs: { param: "var", def: () => "temp", valid: inList(obsOptions) },
  aggType: { param: "daily", def: (s) => aggOptionsFor(s.obs)[0], valid: (v, s) => aggOptionsFor(s.obs).includes(v) },
  period: { param: "days", def: () => "30", valid: inList(periodOpts) },
  chartType: { param: "chart", def: () => "column", valid: inList(["column", "line"]) },
};

export default function Charts() {
  const [{ obs, aggType, period, chartType }, update] = useUrlState(SUMMARY_URL_STATE);
  const aggOpts = aggOptionsFor(obs);

  // Rain only has daily totals; other variables keep their statistic.
  const handleObsChange = (x) => update({ obs: x, aggType: x === "rain" ? "total" : aggType === "total" ? "max" : aggType });
  const setAggType = (value) => update({ aggType: value });
  const setPeriod = (value) => update({ period: value });
  const setChartType = (value) => update({ chartType: value });

  return (
    <Page name="charts" sub="summary" title="Charts | summary">
      <Heading as="h1" size="1" mt="0">
        Summary Charts
      </Heading>

      <Heading size="2" as="h2">
        Daily {fmatAggTypeOpt(aggType)} {OBS.get(obs).name} in the past {period} days
      </Heading>

      <RadioButtonGroup name="obs" value={obs} options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
      <RadioButtonGroup name="agg" value={aggType} options={aggOpts} optFormat={fmatAggTypeOpt} fn={setAggType} />

      <SummaryChart obs={obs} aggType={aggType} chartType={chartType} period={period}  my={4} mx={{base: 0, md: 4, xl: 6}}
       height="responsive" spacing={[20, 20, 25, 10]} />

      <RadioButtonGroup name="period" value={period} options={periodOpts} optFormat={fmatDaysOpt} fn={setPeriod} />
      <RadioButtonGroup name="chart-type" value={chartType} options={["column", "line"]} optFormat={fmatOptCapitalize} fn={setChartType} />

    </Page>
  )
}
