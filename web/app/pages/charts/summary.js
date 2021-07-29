import { Flex, Heading, useRadioGroup } from "@chakra-ui/react";
import { useState } from 'react';
import { SummaryChart } from "../../components/chart";
import { fmatAggTypeOpt, fmatDaysOpt, fmatObsOpt, fmatOptCapitalize, OBS } from '../../components/conf';
import { Page } from "../../components/Page";
import RadioCard from '../../components/RadioCard';


function RadioButtonGroup(props) {
  let { getRootProps, getRadioProps } = useRadioGroup({
    name: props.name,
    defaultValue: props.options[0],
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

export default function Charts() {
  const [obs, setObs] = useState("temp");
  const [aggType, setAggType] = useState("max");
  const [period, setPeriod] = useState("30");
  const [aggOpts, setAggOpts] = useState(["max", "min", "avg"]);
  const [chartType, setChartType] = useState("column");

  const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt"];
  const periodOpts = ["30", "90", "180", "365"];

  const handleObsChange = (x) => {
    setObs(x);
    let aggOptsOk = (x === "rain") ? ["total"] : ["max", "min", "avg"];
    setAggOpts(aggOptsOk);
    if(x === "rain") {
      setAggType("total");
    } else if( aggType === "total" ) {
      setAggType("max");
    }
  }

  return (
    <Page name="charts" sub="summary" title="Charts | summary">
      <Heading as="h1" size="1" mt="0">
        Summary Charts
      </Heading>

      <Heading size="2" as="h2">
        Daily {fmatAggTypeOpt(aggType)} {OBS.get(obs).name} in the past {period} days
      </Heading>

      <RadioButtonGroup name="obs" options={obsOptions} optFormat={fmatObsOpt} fn={handleObsChange} />
      <RadioButtonGroup name="agg" options={aggOpts} optFormat={fmatAggTypeOpt} fn={setAggType} />

      <SummaryChart obs={obs} aggType={aggType} chartType={chartType} period={period}  my={4} mx={{base: 0, md: 4, xl: 6}}
       height="responsive" spacing={[20, 20, 25, 10]} />

      <RadioButtonGroup name="period" options={periodOpts} optFormat={fmatDaysOpt} fn={setPeriod} />
      <RadioButtonGroup name="agg" options={["column", "line"]} optFormat={fmatOptCapitalize} fn={setChartType} />

    </Page>
  )
}
