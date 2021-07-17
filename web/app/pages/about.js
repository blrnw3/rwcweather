import { Heading, Text, Box } from "@chakra-ui/react";
import { Page } from "../components/Page";
import Image from 'next/image';

export default function About() {
    // const data = useDashboard();
  
    return (
      <Page>
        <Heading as="h1">
          About RWC Weather
        </Heading>
        
         <Text>
            RWC Weather is the website for my amateur personal weather station, located in Redwood City, California.
            The station first started collecting data in November 2020 and has been running continously since then.
            This website was hand-built by me in early 2021 with an MVP released on 01 June 2021.
        </Text>

        <Heading as="h2">Location</Heading>
        <Text>
            The station sits approximately 125 m (420 ft) above sea level in the small community of Emerald Lake Hills, which is in the heart of the San Francisco bay area in northern California.
            We are sandwiched between the busy bayside town of Redwood City and the peaceful foothills town of Woodside, which is a few miles west of Palo Alto on the eastern flank of the Santa Cruz mountains.
            The SF bay area is famous for its microclimates and here is no exception. Sitting towards the top of the Emerald Hills canyon, we experience milder winter nights than the valley floor and a degree of protection from the prevailing westerly winds.
            Fog is far less common here than for our neighbours on the Pacific coast and near the Golden Gate, and summer maxima are often 10-15 C (15-30 F) higher.
        </Text>

        <Heading as="h2">Technical specs</Heading>
        <Text>
            The weather station is a wireless Davis VP2 (2020 model) with a WeatherLink Live (WLL) module for data transmission and relay.
            The website is powered by data uploads from Cumulus software, which is running on a local home server (an old Windows 10 machine). Cumulus reads data from WLL and uploads it to the web server.
            The web server is a simple Python Flask application with various worker threads for minimal real-time processing, and more-involved batch workflows for daily, monthly etc. aggregation.
            RWC weather itself is a React application using Next.js. Very much WIP
        </Text>
        
        <Box m="4">
            <Image
                src="/img/map_hq_detail.png"
                alt="HQ map detail - Emerald Hills"
                width={914}
                height={758}
            />
            <Text>
                Station coordinates: approx 37.470, -122.265
            </Text>
            <Image
                src="/img/map_hq_region.png"
                alt="HQ map region - SF bay area"
                width={821}
                height={864}
             />
        </Box>
        
        
      </Page>
    )
  }