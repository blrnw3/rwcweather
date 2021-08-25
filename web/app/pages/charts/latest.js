import { Flex, Heading, Text, useRadioGroup } from "@chakra-ui/react";
import { useState } from 'react';
import { LatestChart } from "../../components/chart";
import { fmatObsOpt, fmatTimeOpt, OBS } from '../../components/conf';
import { Page } from "../../components/Page";
import RadioCard from "../../components/RadioCard";


function RadioButtonGroup(props) {
  let { getRootProps, getRadioProps } = useRadioGroup({
    name: props.name,
    defaultValue: props.default,
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

export default function Charts() {
  const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt"];
  const hrsOptions = ["6", "12", "24", "48", "72", "120", "168", "336", "744", "2208"];

  const [obs, setObs] = useState("temp");
  const [hrs, setHrs] = useState("12");

  return (
    <Page name="charts" sub="latest" title="Charts | latest">
      <Heading as="h1" size="1">
        Latest Charts
      </Heading>
      <Heading as="h2" size="2">
        Last {fmatTimeOpt(hrs)} {fmatObsOpt(obs)}
      </Heading>
      
      <RadioButtonGroup name="obs" options={obsOptions} optFormat={fmatObsOpt} default="temp" fn={setObs} />
      <LatestChart obs={obs} hrs={hrs} my={4} mx={{base: 0, md: 4, xl: 6}} height="responsive" spacing={[20, 20, 25, 10]} />
      <RadioButtonGroup name="hrs" options={hrsOptions} optFormat={fmatTimeOpt} default={"12"} fn={setHrs} />
    </Page>
  )
}
