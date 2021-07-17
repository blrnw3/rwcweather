import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { Heading, Text, Box, useRadio, useRadioGroup, Flex } from "@chakra-ui/react";
import { Page } from "../../components/Page";
import Image from 'next/image';
import { fetcher, OBS } from '../../components/conf';
import useSWR from 'swr';
import { useState } from 'react';
import { unitForObsType } from '../../format';

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
  return <Flex wrap="wrap" id={props.name} {...group}>
    {props.options.map((value) => {
      const radio = getRadioProps({ value });
      return (
        <RadioCard key={value} {...radio}>
          {props.optFormat(value)}
        </RadioCard>
      )
    })}
  </Flex>
}

function fmatObsOpt(obs) {
  return OBS.get(obs).name;
}

function fmatTimeOpt(t) {
  if(t < 50) {
    return t + "h";
  }
  return Math.round(t / 24) + "d";
}

export default function Charts() {
  const obsOptions = ["temp", "wind", "humi", "pres", "aqi", "rain", "wdir", "dewpt"];
  const hrsOptions = [6, 12, 24, 48, 72, 120, 168];

  const [obs, setObs] = useState("temp");
  const [hrs, setHrs] = useState(12);

  return (
    <Page>
      <Heading as="h1">
        Charts
      </Heading>
      <Text fontSize="xl" marginBottom="2">
        Latest weather charts for Redwood City, CA
      </Text>
      
      <RadioButtonGroup name="obs" options={obsOptions} optFormat={fmatObsOpt} default="temp" fn={setObs} />
      <LatestChart obs={obs} hrs={hrs} />
      <RadioButtonGroup name="hrs" options={hrsOptions} optFormat={fmatTimeOpt} default={12} fn={setHrs} />
    </Page>
  )
}