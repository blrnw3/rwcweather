import { Flex, Heading, useRadioGroup } from "@chakra-ui/react";
import { LatestChart } from "../../components/chart";
import { baseObs, fmatObsOpt, fmatTimeOpt, OBS } from '../../components/conf';
import { Page } from "../../components/Page";
import { MINUTE_OBS_STATES, REPORT_OBS_OPTIONS, SunViewToggle } from "../../components/report";
import { inList, useUrlState } from "../../components/urlState";
import RadioCard from "../../components/RadioCard";


function RadioButtonGroup(props) {
  let { getRootProps, getRadioProps } = useRadioGroup({
    name: props.name,
    value: props.value,
    onChange: props.fn,
  })
  const group = getRootProps()
  return <Flex wrap="wrap" id={props.name} {...group}>
    {props.options.map((value) => {
      const radio = getRadioProps({ value });
      return (
        <RadioCard key={value} box={{fontSize: {base: "sm", md: "md"}}} {...radio}>
          {props.optFormat(value)}
        </RadioCard>
      )
    })}
  </Flex>
}

const obsOptions = REPORT_OBS_OPTIONS;
const hrsOptions = ["6", "12", "24", "48", "72", "120", "168", "336", "744", "2208"];

// Selections kept in the URL, e.g. /charts/latest?var=wind&hours=48
const LATEST_URL_STATE = {
  obs: { param: "var", def: () => "temp", valid: inList(MINUTE_OBS_STATES) },
  hrs: { param: "hours", def: () => "12", valid: inList(hrsOptions) },
};

export default function Charts() {
  const [{ obs, hrs }, update] = useUrlState(LATEST_URL_STATE);
  const setObs = (value) => update({ obs: value });
  const setHrs = (value) => update({ hrs: value });

  return (
    <Page name="charts" sub="latest" title="Charts | latest">
      <Heading as="h1" size="1">
        Latest Charts
      </Heading>
      <Heading as="h2" size="2">
        Last {fmatTimeOpt(hrs)} {OBS.get(obs).name}
      </Heading>
      
      <RadioButtonGroup name="obs" value={baseObs(obs)} options={obsOptions} optFormat={fmatObsOpt} fn={setObs} />
      {baseObs(obs) === "wind" && <SunViewToggle obs={obs} fn={setObs} Group={RadioButtonGroup} summaryMode={false} />}
      <LatestChart obs={obs} hrs={hrs} my={4} mx={{base: 0, md: 4, xl: 6}} height="responsive" spacing={[20, 20, 25, 10]} />
      <RadioButtonGroup name="hrs" value={hrs} options={hrsOptions} optFormat={fmatTimeOpt} fn={setHrs} />
    </Page>
  )
}
