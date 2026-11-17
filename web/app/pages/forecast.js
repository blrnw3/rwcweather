import { Heading, Text } from "@chakra-ui/react";
import { EnsembleRain } from "../components/ensembleRain";
import { NwsForecastSection } from "../components/forecastNws";
import { Meteogram } from "../components/meteogram";
import { Page } from "../components/Page";

export default function ForecastPage() {
  return (
    <Page name="forecast" title="Forecast">
      <Heading as="h1" size="1">Forecast</Heading>
      <Text variant="para" mb="4">
        A 10-day meteogram for the station, the National Weather Service 72-hour forecast and Area Forecast
        Discussion, and ensemble rainfall totals from GEFS and ECMWF. These are external model and office
        products, not a forecast produced by the station itself.
      </Text>
      <Meteogram />
      <NwsForecastSection />
      <EnsembleRain />
    </Page>
  );
}
