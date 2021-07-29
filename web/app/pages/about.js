import { Heading, Text, Box, Link, List, VStack, Tabs, TabList, Tab, TabPanels, TabPanel } from "@chakra-ui/react";
import { Page } from "../components/Page";
import Image from 'next/image';
import { RwcExternalLink } from "../components/custom";

export default function About() {
  // const data = useDashboard();

  return (
    <Page name="more" sub="about" title="About">
      <Heading as="h1" size="1">
        About Redwood City Weather
      </Heading>

      <Text variant="para">
        RWC Weather is the website for my amateur personal weather station, located in Redwood City, California.
        The station first started collecting data in November 2020 and has been running continuously since then.
        This website was hand-built by me in early 2021 with an MVP released in July 2021.
      </Text>

      <Heading as="h2" size="2">Location</Heading>
      <Text variant="para">
        The station sits approximately 125 m (420 ft) above sea level in the small community of Emerald Lake Hills, which is in the heart of the San Francisco bay area in northern California.
        We are sandwiched between the busy bayside town of Redwood City and the peaceful foothills town of Woodside, which is a few miles west of Palo Alto on the eastern flank of the Santa Cruz mountains.
        The SF bay area is famous for its microclimates and here is no exception. Sitting towards the top of the Emerald Hills canyon, we experience milder winter nights than the valley floor and a degree of protection from the prevailing westerly winds.
        Fog is far less common here than for our neighbours on the Pacific coast and near the Golden Gate, and summer maxima are often 10-15 C (15-30 F) higher.
      </Text>

      <Tabs colorScheme="brand">
        <TabList>
          <Tab>Local</Tab>
          <Tab>Regional</Tab>
        </TabList>

        <TabPanels>
          <TabPanel>
            <Image
              src="/img/map_hq_detail.png"
              alt="HQ map detail - Emerald Hills"
              width={914}
              priority
              height={758}
              quality={90}
            />
          </TabPanel>
          <TabPanel>
            <Image
              src="/img/map_hq_region.png"
              alt="HQ map region - SF bay area"
              width={821}
              placeholder="blur"
              height={864}
              quality={90}
            />
          </TabPanel>
        </TabPanels>
      </Tabs>
      <Text mb="4">
        Station coordinates: approx <RwcExternalLink href="https://www.google.com/maps/@37.47,-122.265,13z">37.470, -122.265</RwcExternalLink>
      </Text>

      <Heading as="h2" size="2">Technical specs</Heading>
      <Text variant="para">
        The weather station is a wireless Davis VP2 (2020 model) with a WeatherLink Live (WLL) module for data transmission and relay.
        The website is powered by data uploads from Cumulus software, which is running on a local home server (an old Windows 10 machine). Cumulus reads data from WLL and uploads it to the web server.
      </Text>
      <Text variant="para">
        The web server is a simple Python Flask application with various worker threads for both minimal real-time processing and batch workflows for data aggregation.
        RWC weather itself is a React application using Next.js and the Chakra-UI CSS framework / component lib. It's rather WIP, and my first time using React. 
        I haven't done front-end for about 10 years, and boy does the tech and best-practices change rapidly.
      </Text>

      <Heading as="h3" size="3">Sensor siting</Heading>

      <Text variant="para">
        Pictures of the sensors are below. The siting is not optimal:<br />
        The T/H sensor is overexposed to the sun so likely reads too high in the afternoons. The rain sensor has an excessive rain shadow so likely undereads.
        Finally the wind sensor is too close to the ground and other objects, causing it to underead. Improving these siting conditions is a project for another day :)
      </Text>

      <Tabs colorScheme="brand">
        <TabList>
          <Tab>Temperature, humidity, rain</Tab>
          <Tab>Wind</Tab>
        </TabList>

        <TabPanels>
          <TabPanel>
            <Image
              src="/img/iss.jpeg"
              alt="Integrated sensor suite"
              priority
              width={1008}
              height={756}
            />
          </TabPanel>
          <TabPanel>
            <Image
              src="/img/wind_sensor.jpeg"
              alt="Wind sensor"
              placeholder="blur"
              width={1008}
              height={756}
            />
          </TabPanel>
        </TabPanels>
      </Tabs>


      <Heading as="h2" size="2">About me</Heading>
      <Text variant="para">
        I also run a weather station in Hampstead, London, which I set up in 2010 and now operates semi-autonomously at my mother's house.
        It has a website, <RwcExternalLink href="http://nw3weather.co.uk">nw3weather</RwcExternalLink>,
        which has been running since then and has now accumulated a rich archive of data.
      </Text>
      <Text variant="para">
        I have been in the SF bay area since 2018 and currently live and <RwcExternalLink href="https://www.linkedin.com/in/ben-masschelein-rodgers-b31744b1/">work</RwcExternalLink> in Redwood City.
        I am here with my wife, as well as my cat Eleanor.
        This website is dedicated to my now tragically-deceased cat, Pliny: an affectionate, funny, playful orange tabby who inspired the color scheme for RWC weather.
      </Text>

      <Heading as="h3" size="3" id="contact">Contact</Heading>
      <VStack align="left">
        <Text><b>Email:</b> bmr[at]nw3weather.co.uk</Text>
        <Text><b>Github:</b> <RwcExternalLink href="https://github.com/blrnw3">blrnw3</RwcExternalLink> </Text>
        <Text><b>Twitter:</b> <RwcExternalLink href="https://twitter.com/rwcweather1">rwcweather1</RwcExternalLink> </Text>
      </VStack>

    </Page>
  )
}