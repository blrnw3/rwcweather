import {
  Box,
  Button, Text,
  Flex, Link as ChakraLink,
  Menu,
  MenuButton, MenuItem,
  MenuList, Tooltip, useDisclosure, Modal, ModalOverlay, ModalContent, ModalHeader, ModalCloseButton, ModalBody, ModalFooter, RadioGroup, Stack, Radio
} from '@chakra-ui/react';
import { createContext, useEffect, useState } from 'react';
import { IoSettingsOutline } from 'react-icons/io5';
import { useRouter } from 'next/router';
import Layout from './Layout';
import { BrandBanner, LiveStrip } from './BrandBanner';


export const UnitCtx = createContext(null);

const NAV = new Map([
  ["home", "/"],
  ["reports", new Map([
    ["daily", "/reports/day"],
    ["annual", "/reports/matrix"],
    ["all-time", "/reports/alltime"],
    ["ranking", "/reports/ranking"],
    ["climate", "/reports/climate"]
  ])],
  ["charts", new Map([
    ["latest", "/charts/latest"],
    ["summary", "/charts/summary"],
    ["year", "/charts/year"]
  ])],
  ["more", new Map([
    ["about", "/about"],
  ])],
]);

// Pages that take a ?var= selection. Following a nav link between them keeps the variable being
// viewed (including the sunshine Hours / % of possible view, which is part of var); a page that
// doesn't support that variable falls back to its own default (see useUrlState validation).
const VAR_PAGES = new Set(["/reports/day", "/reports/matrix", "/reports/alltime", "/reports/ranking",
  "/charts/latest", "/charts/summary", "/charts/year"]);

export function carryVarHref(to, query) {
  const v = query?.var;
  if (!VAR_PAGES.has(to) || typeof v !== "string" || !/^[a-z]+$/.test(v)) {
    return to;
  }
  // The daily report has sunshine hours but no "% of possible" view.
  const dayVar = { sunpct: "sun", wet: "rain", wetrate: "rain", rain60: "rain", rain10: "rain" };
  return to + "?var=" + encodeURIComponent(to === "/reports/day" && dayVar[v] ? dayVar[v] : v);
}

function useCarryHref() {
  const router = useRouter();
  const fromVarPage = router && VAR_PAGES.has(router.pathname);
  return (to) => fromVarPage ? carryVarHref(to, router.query) : to;
}

function NavBarItem(props) {
  let bcol = (props.activePage === props.name) ? "yellow" : "#fd9800";
  let wgt = (props.activePage === props.name) ? "bold" : "medium";
  let border = "4px solid " + bcol;
  let bg = "pliny.700";
  let col = "white";

  if (props.menu) {
    return <MenuButton as={Box} p={{base: 2, md: 4}} color={col} fontWeight={wgt} borderTop={border} _hover={{ bg: bg, cursor: "pointer" }}
      textTransform="capitalize">
      {props.name}
    </MenuButton>
  } else {
    return <Box as="a" p={{base: 2, md: 4}} color="white" fontWeight={wgt} borderTop={border} _hover={{ bg: bg }} href={props.to}
      textTransform="capitalize">
      {props.name}
    </Box>;
  }
}

function NavBarMenuItem(props) {
  return <MenuItem as="a" px={{base: 3, md: 6}} py={5} color="white" _hover={{ backgroundColor: "pliny.700" }} href={props.to} textTransform="capitalize">
    {props.name}
  </MenuItem>;
}

function SubNavBarItem(props) {
  let col = (props.activePage === props.name) ? "orange" : "inherit";
  let wgt = (props.activePage === props.name) ? "bold" : "medium";
  return <Box as="a" py="2" px="3" color="gray.700" fontWeight={wgt} textTransform="capitalize"
    borderBottom={"2px solid " + col} _hover={{ backgroundColor: "pliny.300" }}
    href={props.to}>
    {props.name}
  </Box>;
}

function SettingsModal(props) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  return (
    <Box ml={{base: 2, sm: 4, md: 5, xl: 7}} py={{base: 2, md: 4}} color="yellow">
      <Button fontSize="xl" p={{base: 2, md: 4}} _hover={{ backgroundColor: "pliny.700" }} onClick={onOpen} bg="none">
        <IoSettingsOutline />
      </Button>

      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent color="gray.100" bg="pliny.800">
          <ModalHeader>Global settings</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text fontSize="lg">Units:</Text>
            <RadioGroup onChange={props.setUnit} value={props.unit}>
              <Stack direction="row">
                <Radio value="us">🇺🇸 Weird</Radio>
                <Radio value="eu">🇪🇺 Modern</Radio>
                <Radio value="uk">🇬🇧 Correct</Radio>
              </Stack>
            </RadioGroup>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="pliny" mr={2} onClick={onClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  )
}

function Header(props) {
  const carry = useCarryHref();
  return <Box id="header" w="100%" bg="pliny.500">
    <BrandBanner unit={props.unit} />
    <Flex w="100%" justify="space-between" align="flex-end" wrap="wrap" px={{ base: 2, md: 4 }} bg="pliny.800">
    <LiveStrip unit={props.unit} />
    <Flex id="nav" wrap="wrap" alignSelf="flex-end" ml="auto">
      {Array.from(NAV).map(([nav, subnavObj]) => {
        if (typeof (subnavObj) === "string") {
          return <NavBarItem key={nav} name={nav} to={subnavObj} activePage={props.name} />
        } else {
          return <Menu key={nav} gutter="0">
            <NavBarItem name={nav} menu activePage={props.name} />
            <MenuList p="0" border="none" borderRadius="0" bg="pliny.500">
              {Array.from(subnavObj).map(([subnav, to]) => {
                return <NavBarMenuItem key={subnav} name={subnav} to={carry(to)} />
              })}
            </MenuList>
          </Menu>
        }
      })}
      <SettingsModal setUnit={props.setUnit} unit={props.unit} />
    </Flex>
    </Flex>
  </Box>
}

function SubHeader(props) {
  const carry = useCarryHref();
  const subnav = (typeof(NAV.get(props.name)) === "string") ? new Map([]) : NAV.get(props.name);
  return <Flex id="subheader" bg="pliny.50" justify="space-between">
    <Flex>
      {" "}
    </Flex>
    <Flex id="subnav" alignSelf="flex-end" mr="20">
      {Array.from(subnav).map(([subnav, to]) => {
        return <SubNavBarItem key={subnav} name={subnav} to={carry(to)} activePage={props.sub} />
      })}
    </Flex>
  </Flex>
}

function Footer(props) {
  return <Flex id="footer" py={{base: 5, md: 8}} bg="pliny.800" color="gray.50" justify="space-evenly" wrap="wrap"
    lineHeight={{base: 6, lg: 7}} alignItems="flex-end">
    <Box>
      <ChakraLink variant="subtle" color="inherit" href="/" display="block">Dashboard</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/reports/day" display="block">Daily Report</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/reports/matrix" display="block">Data Matrix</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/reports/alltime" display="block">All-time</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/reports/ranking" display="block">Rankings</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/reports/climate" display="block">Climate</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/charts/latest" display="block">Latest Charts</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/charts/summary" display="block">Summary Charts</ChakraLink>
      <ChakraLink variant="subtle" color="inherit" href="/charts/year" display="block">Year Charts</ChakraLink>
    </Box>
    <Box m={3}>
      <Text>
        ⚒️ &nbsp;Built by&nbsp;<Tooltip label="Email: bmr[at]nw3weather.co.uk">Ben Masschelein-Rodgers</Tooltip>
      </Text>
      <Text>
        🧡 &nbsp;<ChakraLink isExternal href="/img/pliny_patio.jpg" title="Chilling on the patio" variant="hidden">For Pliny</ChakraLink>
        , who
        {' '}<ChakraLink isExternal href="/img/pliny_frolic.jpg" title="Frolicking in the spring greenery" variant="hidden">loved to be outside</ChakraLink>
      </Text>
      <Text>🌦️ &nbsp;Sister station:{' '} <ChakraLink color="green.50" variant="subtle" isExternal
        href="http://nw3weather.co.uk"
      >London NW3 weather</ChakraLink>
      </Text>
    </Box>
    <Box m={3}>
      <ChakraLink variant="subtle" color="inherit" href="/about#contact">Contact / social</ChakraLink>
      <Text>Made in Redwood City, CA</Text>
      <Text>&copy; rwcweather 2021-{new Date().getFullYear()}</Text>
    </Box>
  </Flex>
}

export function Page(props) {
  const [unit, setUnit] = useState(((typeof window !== "undefined") ? localStorage.getItem("unit") : null) || "us");

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("unit", unit);
    }
  });

  // const { colorMode } = useColorMode()
  const color = { light: 'black', dark: 'black' }
  return (
    <Layout title={props.title}>
    <Box id="container" w="100%" minHeight="1000px" bg="pliny.900"
      color={color.light}>
      <Box id="page" m="0% auto" maxWidth="1620px">
        <Header {...props} unit={unit} setUnit={setUnit} />
        <SubHeader {...props} />
        <Box id="body" py={{base: 2, md: 3, lg: 4, xl: 5}} px={{base: 2, sm: 3, md: 4, lg: 6, xl: 7}} bg="gray.50">
          <UnitCtx.Provider value={unit}>
            {props.children}
          </UnitCtx.Provider>
        </Box>
        <Footer />
      </Box>
    </Box>
    </Layout>
  )
}
