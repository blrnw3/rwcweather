import { Box, Flex, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import useSWR from 'swr';
import { fetcher } from './conf';
import { formatObs } from '../format';
import { HERO_PHOTO, SEASONAL_PHOTOS, seasonOf } from './bannerPhotos';

function BannerHero() {
  return <>
    <Box as="img" src={HERO_PHOTO} alt="" aria-hidden="true" position="absolute" top="0" left="0" w="100%" h="100%"
      objectFit="cover" objectPosition="left center" zIndex="0" />
    {/* dark gradient keeps the wordmark/tagline legible */}
    <Box position="absolute" top="0" left="0" w="100%" h="100%" zIndex="0"
      bgGradient="linear(to-r, rgba(32,11,0,0.72), rgba(32,11,0,0.35) 45%, rgba(32,11,0,0.1))" />
  </>;
}

// Photo slots on the right of the banner (like nw3). Empty list = SVG art only.
function BannerPhotos() {
  // Seasonal set; picked after mount so server and client render match.
  const [season, setSeason] = useState(null);
  useEffect(() => {
    setSeason(seasonOf(new Date().getMonth()));
  }, []);
  const shown = (season && SEASONAL_PHOTOS[season]) || [];
  if (!shown.length) {
    return null;
  }
  return <Flex position="absolute" top="0" right="0" h="100%" zIndex="0" display={{ base: "none", md: "flex" }}>
    {shown.slice(0, 3).map((p, i) => <Box key={p.src} as="img" src={p.src} alt={p.alt || ""} title={p.alt} h="100%" objectFit="cover"
      w={{ md: "200px", lg: "260px" }} display={{ md: i < 1 ? "block" : "none", lg: "block" }}
      borderLeft="3px solid" borderColor="pliny.800" />)}
  </Flex>;
}

export function LiveStrip({ unit }) {
  const { data } = useSWR(`/api/web/dashboard/live`, fetcher, { refreshInterval: 60000, revalidateOnFocus: false });
  const res = data?.result;
  if (!res?.now) {
    return null;
  }
  const items = [
    ["Temp", formatObs(unit, res.now.temp, "temp")],
  ];
  const rainToday = res.today?.rain?.total;
  if (rainToday > 0) {
    items.push(["Rain today", formatObs(unit, rainToday, "rain")]);
  }
  return <Flex id="live-wx" gap={{ base: 3, md: 4 }} fontSize={{ base: "xs", md: "sm" }} color="pliny.50"
    pl={{ base: 2, md: 3 }} pr={2} py={2} alignSelf="center" wrap="wrap" whiteSpace="nowrap"
    title="Current conditions">
    {items.map(([k, v]) => <Box key={k}>
      <Text as="span" color="pliny.200" mr={1}>{k}</Text>
      <Text as="span" fontWeight="semibold">{v}</Text>
    </Box>)}
  </Flex>;
}

export function BrandBanner({ unit }) {
  return <Box id="banner" position="relative" overflow="hidden" minH={{ base: "104px", md: "132px" }}>
    <BannerHero />
    <BannerPhotos />
    <Flex position="relative" zIndex="1" h="100%" minH="inherit" px={{ base: 4, md: 7 }} py={{ base: 3, md: 4 }}
      direction={{ base: "column", md: "row" }} justify="space-between" align={{ base: "flex-start", md: "flex-end" }}
      gap={2}>
      <Box as="a" href="/" _hover={{ textDecoration: "none" }} textShadow="0 2px 6px rgba(0,0,0,0.45)">
        <Box lineHeight="1" fontSize={{ base: "4xl", md: "6xl" }} letterSpacing="-1px" color="pliny.50">
          <Text as="span" fontWeight="black" color="yellow.300">rwc</Text>
          <Text as="span" fontWeight="light" ml={1}>weather</Text>
        </Box>
        <Text mt={1} fontSize={{ base: "xs", md: "md" }} color="pliny.100" letterSpacing={{ base: "0.5px", md: "2px" }}
          textTransform="uppercase">
          Emerald Lake Hills · Redwood City, CA · 420 ft
        </Text>
      </Box>
    </Flex>
  </Box>;
}
