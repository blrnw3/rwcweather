import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { Heading, Text, Box, useRadio, useRadioGroup, HStack } from "@chakra-ui/react";
import { Page } from "../components/Page";
import Image from 'next/image';
import { fetcher } from '../components/conf';
import useSWR from 'swr';
import { useState } from 'react';

function useLatest (mins) {
    const { data, error } = useSWR("/api/obs/latest?d="+ mins, fetcher, {refreshInterval: 60000})
    if (error || !data) {
      console.log(error);
      return error ? 0 : null;
    }
    let res = data["result"];
    return res;
  }

function LatestChart(props) {
    let obs = props.obs;
    let hrs = props.hrs;
    const latest = useLatest(hrs * 60);
    let temp;
    if(!latest) {
        temp = [[0, 0]];
    } else {
        temp = latest.map(x => [x["t"], x[obs]]).reverse();
    }
    let options = {
        credits: {
            href: null,
            text: "@rwcweather"
        },
        title: {
          text: "Redwood City weather, last "+ hrs +" hrs " + obs
        },
        time: {
            timezoneOffset: 60 * 7
        },
        xAxis: {
            type: "datetime"
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

// 1. Create a component that consumes the `useRadio` hook
function RadioCard(props) {
  const { getInputProps, getCheckboxProps } = useRadio(props)

  const input = getInputProps()
  const checkbox = getCheckboxProps()

  return (
    <Box as="label">
      <input {...input} />
      <Box
        {...checkbox}
        cursor="pointer"
        borderWidth="1px"
        borderRadius="md"
        boxShadow="md"
        _checked={{
          bg: "teal.600",
          color: "white",
          borderColor: "teal.600",
        }}
        _focus={{
          boxShadow: "outline",
        }}
        px={5}
        py={3}
      >
        {props.children}
      </Box>
    </Box>
  )
}

function RadioButtonGroup(props) {
  let { getRootProps, getRadioProps } = useRadioGroup({
    name: props.name,
    defaultValue: props.default,
    onChange: props.fn,
  })
  const group = getRootProps()
  return <HStack {...group}>
    {props.options.map((value) => {
      const radio = getRadioProps({ value })
      return (
        <RadioCard key={value} {...radio}>
          {value}
        </RadioCard>
      )
    })}
  </HStack>
}

export default function Charts() {
  const obsOptions = ["temp", "wind", "humi", "pres", "pm2", "rain", "wdir", "dewpt"];
  const hrsOptions = [6, 12, 24, 48, 72, 120, 148];

  const [obs, setObs] = useState("temp");
  const [hrs, setHrs] = useState(12);

  return (
    <Page>
      <Heading as="h1">
        Charts
      </Heading>
      
        <Text>
          Latest weather charts for Redwood City, CA
      </Text>
      
      <RadioButtonGroup name="obs" options={obsOptions} default="temp" fn={setObs} />
      
      <LatestChart obs={obs} hrs={hrs} />

      <RadioButtonGroup name="hrs" options={hrsOptions} default={12} fn={setHrs} />

      
    </Page>
  )
}