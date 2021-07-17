import Highcharts from 'highcharts'
import HighchartsReact from 'highcharts-react-official'
import { Heading, Text, Box, useRadio, useRadioGroup, HStack, Grid, GridItem } from "@chakra-ui/react";
import { Page } from "../../components/Page";
import Image from 'next/image';
import { fetcher } from '../../components/conf';
import useSWR from 'swr';
import { useState } from 'react';
import { formatObs, prettySecs, timeOf } from '../../format';
import { OBS } from '../../components/conf';
import Select from '../../components/ChakraReactSelect'
import ReactSelect, { components as selectComponents } from "react-select";
import { Fragment } from 'react';

function useSummary (obs, agg) {
    const { data, error } = useSWR("/api/obsvar/summary/"+ obs +"/"+agg, fetcher, {refreshInterval: 300000})
    if (error || !data) {
      console.log(error);
      return error ? {} : {};
    }
    let res = data["result"];
    return res;
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
        id="obs-select"
        name="obs"
        isSearchable={false}
        options={opts}
        defaultValue={opts[0]}
        onChange={props.fnObs}
      />
    <ReactSelect
      id="aggtype-select"
      name="agg_type"
      isSearchable={false}
      options={aggOpts}
      defaultValue={aggOpts[0]}
      onChange={props.fnAgg}
    />
    </Box>
}

function DailyMatrix(props) {
    const obs = props.obs || "temp";
    const agg = props.aggType || "max";
    const res = useSummary(obs, agg)?.daily || [];
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    // Convert input to matrix structure (map of month->array<day>)
    let data = new Map();
    for(let r of res) {
        let mon = months[r["d"][1] - 1];
        if(!data.has(mon)) {
            data.set(mon, Array(31));
        }
        data.get(mon)[r["d"][2]] = r["val"];
    }

    return <Grid id="obs-matrix-days"
        templateColumns="1.2fr repeat(12, 1fr)"
        templateRows="30px auto"
        overflow="auto"
    >
        <Box>🌧️</Box>
        {months.map((m) => {
            return <Box key={m} fontWeight="bold">{m}</Box>
        })}
        {Array.from(Array(31).keys()).map((i) => {
            let d = i + 1;
            return <Fragment key={"dm-frag-" + d.toString()}>
                <Box className="day" key={d.toString()}>{d}</Box>
                {months.map((m) => {
                    let v = (data.has(m) ? formatObs(data.get(m)[d], OBS.get(obs).fmat, false, false) : null) || "-";
                    return <Box key={m + "-" + d.toString()}
                            maxWidth="100px"
                            >
                        {v}</Box>
                })}
            </Fragment>
        })}
    </Grid>
}

function MonthlyMatrix(props) {
    const obs = props.obs || "temp";
    const agg = props.aggType || "max";
    const res = useSummary(obs, agg)?.monthly || [];
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    
    const summaries = new Map();
    summaries.set("min_val", "Min");
    summaries.set("max_val", "Max");
    summaries.set(OBS.get(obs).summary, (OBS.get(obs).summary == "avg") ? "Avg" : "Total");
  
    // Convert input to matrix structure (map of month->summary_obj)
  let data = new Map();
  for(let r of res) {
      let mon = months[r["m"][1] - 1];
      data.set(mon, r["summary"]);
  }

  return <Grid id="obs-matrix-months" key="obs-matrix-months"
        templateColumns="1.2fr repeat(12, 1fr)"
        templateRows="40px auto"
        overflow="auto"
    >
        <Box key="mm-base" id="mm-base">🌧️</Box>
        {months.map((m) => {
            return <Box key={m} id={m} fontWeight="bold">{m}</Box>
        })}
        {Array.from(summaries, ([k, val])  => {
            return <Fragment key={"mm-frag-" + k}>
                <Box className="summary" id={k} key={k}>{val}</Box>
                {months.map((m) => {
                    let v = (data.has(m) ? formatObs(data.get(m)[k], OBS.get(obs).fmat, false, false) : null) || "-";
                    return <Box key={m + "-" + k} id={m + "-" + k}
                            maxWidth="100px"
                            >
                        {v}</Box>
                })}
            </Fragment>
        })}
    </Grid>

}

export default function Obs() {

  const [obs, setObs] = useState(null);
  const [aggType, setAggType] = useState(null);

  return <Page>
      <Heading as="h1">
        Daily {aggType} {obs} this year 
      </Heading>
            
      <SummaryObsSelect fnObs={x => setObs(x.value)} fnAgg={x => setAggType(x.value)} />
      
      <DailyMatrix obs={obs} aggType={aggType} />
      
      <MonthlyMatrix obs={obs} aggType={aggType} />

    </Page>
  
}