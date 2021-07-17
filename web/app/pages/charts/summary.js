import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { Heading, Text, Box, useRadio, useRadioGroup, HStack } from "@chakra-ui/react";
import { Page } from "../../components/Page";
import Image from 'next/image';
import { fetcher } from '../../components/conf';
import useSWR from 'swr';
import { useState } from 'react';
import { formatObs, prettySecs, timeOf } from '../../format';
import { OBS } from '../../components/conf';
import Select from '../../components/ChakraReactSelect'
import ReactSelect, { components as selectComponents } from "react-select";

function useSummary (obs, agg) {
    const { data, error } = useSWR("/api/obs/summary/"+ obs +"/"+agg, fetcher, {refreshInterval: 300000})
    if (error || !data) {
      console.log(error);
      return error ? 0 : null;
    }
    let res = data["result"];
    return res;
  }

function SummaryChart(props) {
    let obs = props.obs || "temp";
    let aggType = props.aggType || "max";
    if(aggType === "avg" && obs === "rain") {
      aggType = "total";
    }
    const latest = useSummary(obs, aggType);
    let data;
    if(!latest) {
        data = [[0, 0]];
    } else {
        data = latest.map(x => [new Date(x["d"][0], x["d"][1] -1, x["d"][2]).valueOf(), x["val"]]).reverse();
    }
    let options = {
        credits: {
            href: null,
            text: "@rwcweather"
        },
        title: {
          text: "Chart of " + aggType + " " + obs + ""
        },
        time: {
            timezoneOffset: 60 * 7
        },
        xAxis: {
            type: "datetime"
        },
        series: [{
          data: data,
          name: aggType + " " + obs
        }]
      }
    return <Box m="4">
        <HighchartsReact
            highcharts={Highcharts}
            options={options}
        />
    </Box>
}

function SummaryObsSelect(props) {
  let opts = Array.from(OBS, ([k, v]) => ({value: k, label: v.name}))
  const aggOpts = [
    {value: "max", label: "Max"},
    {value: "min", label: "Min"},
    {value: "avg", label: "Average"},
  ]
  return <Box>
      <ReactSelect
        name="obs"
        isSearchable={false}
        options={opts}
        defaultValue={opts[0]}
        onChange={props.fnObs}
      />
    <Select
      name="agg_type"
      isSearchable={false}
      options={aggOpts}
      defaultValue={aggOpts[0]}
      onChange={props.fnAgg}
    />
    </Box>
}

export default function Charts() {

  const [obs, setObs] = useState(null);
  const [aggType, setAggType] = useState(null);

  return (
    <Page>
      <Heading as="h1">
        Summary Charts
      </Heading>
      
      <Text>
        Latest weather summary charts for Redwood City, CA
      </Text>
      
      <SummaryObsSelect fnObs={x => setObs(x.value)} fnAgg={x => setAggType(x.value)} />
      
      <SummaryChart obs={obs} aggType={aggType} />
      
    </Page>
  )
}