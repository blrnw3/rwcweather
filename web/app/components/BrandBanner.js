import { Box, Flex, Text } from '@chakra-ui/react';
import useSWR from 'swr';
import { fetcher } from './conf';
import { formatObs } from '../format';

// Stylised Emerald Lake Hills skyline: layered ridges with redwood silhouettes against a
// dusk sky. Pure SVG (no photos), scales to any width; preserveAspectRatio slices on phones.
function Redwood({ x, base, h }) {
  const w = h * 0.22;
  // stacked triangles for a tall, narrow conifer
  const tiers = [0, 0.22, 0.42, 0.6];
  return <g>
    <rect x={x - w * 0.06} y={base - h * 0.12} width={w * 0.12} height={h * 0.12} />
    {tiers.map((t, i) => {
      const top = base - h + t * h;
      const bottom = base - h * 0.08 - (tiers.length - 1 - i) * h * 0.06;
      const half = w * (0.35 + i * 0.2);
      return <polygon key={i} points={`${x},${top} ${x - half},${bottom} ${x + half},${bottom}`} />;
    })}
  </g>;
}

const TREES_BACK = [[60, 34], [95, 44], [130, 38], [520, 30], [548, 40], [578, 34], [1150, 38], [1185, 46], [1220, 36], [1470, 42], [1505, 34]];
const TREES_FRONT = [[22, 82], [58, 108], [96, 90], [134, 70], [1310, 74], [1350, 104], [1392, 88], [1440, 116], [1490, 80], [1560, 98], [1600, 84]];

export function BannerArt() {
  return <Box as="svg" viewBox="0 0 1620 140" preserveAspectRatio="xMaxYMax slice" position="absolute"
    top="0" left="0" w="100%" h="100%" aria-hidden="true" zIndex="0">
    <defs>
      <linearGradient id="bn-sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#4f2600" />
        <stop offset="0.55" stopColor="#b35c00" />
        <stop offset="1" stopColor="#ffa94c" />
      </linearGradient>
      <radialGradient id="bn-sun" cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor="#fff2da" stopOpacity="0.95" />
        <stop offset="1" stopColor="#ffd9ae" stopOpacity="0" />
      </radialGradient>
    </defs>
    <rect width="1620" height="140" fill="url(#bn-sky)" />
    <circle cx="1010" cy="96" r="70" fill="url(#bn-sun)" />
    <circle cx="1010" cy="100" r="16" fill="#fff2da" opacity="0.9" />
    {/* far ridge (Santa Cruz Mtns) */}
    <path d="M0 100 C120 80 220 92 330 78 S560 70 700 86 S930 66 1080 80 S1330 70 1450 84 S1580 78 1620 82 V140 H0Z"
      fill="#814100" opacity="0.65" />
    <g fill="#5c2f00" opacity="0.8">
      {TREES_BACK.map(([x, h]) => <Redwood key={x} x={x} base={96} h={h} />)}
    </g>
    {/* mid ridge (Emerald Hills) */}
    <path d="M0 116 C150 98 260 112 420 102 S700 120 860 106 S1120 96 1280 110 S1520 100 1620 108 V140 H0Z"
      fill="#4f2600" />
    {/* near ridge with redwoods */}
    <path d="M0 128 C200 118 380 132 600 124 S1000 134 1200 124 S1500 130 1620 122 V140 H0Z" fill="#200b00" />
    <g fill="#200b00">
      {TREES_FRONT.map(([x, h]) => <Redwood key={x} x={x} base={130} h={h} />)}
    </g>
  </Box>;
}

export function LiveStrip({ unit }) {
  const { data } = useSWR(`/api/web/dashboard/live`, fetcher, { refreshInterval: 60000, revalidateOnFocus: false });
  const res = data?.result;
  if (!res?.now) {
    return null;
  }
  const items = [
    ["Temp", formatObs(unit, res.now.temp, "temp")],
    ["Rain today", formatObs(unit, res.today?.rain?.total, "rain")],
    ["Wind", formatObs(unit, res.now.wind, "wind") + " " + formatObs(unit, res.now.wdir, "wdir")],
  ];
  return <Flex id="live-wx" gap={{ base: 3, md: 4 }} fontSize={{ base: "xs", md: "sm" }} color="pliny.50"
    px={{ base: 2, md: 3 }} py={2} wrap="wrap" whiteSpace="nowrap"
    title="Current conditions">
    {items.map(([k, v]) => <Box key={k}>
      <Text as="span" color="pliny.200" mr={1}>{k}</Text>
      <Text as="span" fontWeight="semibold">{v}</Text>
    </Box>)}
  </Flex>;
}

export function BrandBanner({ unit }) {
  return <Box id="banner" position="relative" overflow="hidden" minH={{ base: "104px", md: "132px" }}>
    <BannerArt />
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
