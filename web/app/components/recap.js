import { Box, Flex, Link, ListItem, OrderedList, Spinner, Text, UnorderedList, useRadioGroup } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import useSWR from "swr";
import { fetcher } from './conf';
import RadioCard from './RadioCard';

// Written recaps (GET /api/recap/latest): yesterday, the month so far and last month.
// The API sends the text as parsed blocks (see rwcwx/recap/markdown.py): paragraphs, lists, bold and vetted
// http(s) links only. They are mapped to React elements here, so all text is escaped by React and no HTML
// string is ever injected; link targets are checked again before use.

const KINDS = ["day", "month_to_date", "month"];
const TAB_NAMES = { day: "Yesterday", month_to_date: "Month so far", month: "Last month" };
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];
const SAFE_HREF = /^https?:\/\/[^\s"'<>`\\]+$/i;
const PT = "America/Los_Angeles";

export function useRecap() {
  const { data, error } = useSWR("/api/recap/latest", fetcher, { refreshInterval: 600000 });
  return { recap: data?.result, error, loading: !data && !error };
}

function utcDate(period) {
  const [y, m, d] = period.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d || 1));
}

export function periodLabel(entry) {
  const p = entry.period;
  if (entry.kind === "day") {
    return new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC" })
      .format(utcDate(p));
  }
  const [y, m] = p.split("-").map(Number);
  if (entry.kind === "month_to_date" && entry.generated_at) {
    // Written in the morning about the days up to yesterday: "October 1–26, 2026".
    const gen = new Intl.DateTimeFormat("en-CA", { timeZone: PT }).format(new Date(entry.generated_at)).split("-").map(Number);
    if (gen[0] === y && gen[1] === m && gen[2] > 2) {
      return MONTHS[m - 1] + " 1–" + (gen[2] - 1) + ", " + y;
    }
    return MONTHS[m - 1] + " " + y + " so far";
  }
  return MONTHS[m - 1] + " " + y;
}

function updatedLabel(iso) {
  if (!iso) return null;
  return new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: PT })
    .format(new Date(iso)) + " PT";
}

function Inlines({ nodes }) {
  return (nodes || []).map((n, i) => {
    if (n.t === "text") {
      return <Text as="span" key={i}>{n.v}</Text>;
    }
    if (n.t === "b") {
      return <Text as="strong" key={i} fontWeight="bold"><Inlines nodes={n.c} /></Text>;
    }
    if (n.t === "a" && typeof n.href === "string" && SAFE_HREF.test(n.href)) {
      const external = !/^https?:\/\/(www\.)?rwcweather\.com(\/|$)/i.test(n.href);
      return <Link key={i} href={n.href} rel="noopener nofollow" target={external ? "_blank" : undefined}
        textDecoration="underline">{n.v}</Link>;
    }
    return <Text as="span" key={i}>{n.v || ""}</Text>;
  });
}

export function RecapBody({ blocks }) {
  return <Box className="recap-body" fontSize="sm" lineHeight="short">
    {(blocks || []).map((b, i) => {
      if (b.t === "ul" || b.t === "ol") {
        const List = b.t === "ul" ? UnorderedList : OrderedList;
        return <List key={i} ml="5" mb="2" spacing="1">
          {(b.items || []).map((item, j) => <ListItem key={j}><Inlines nodes={item} /></ListItem>)}
        </List>;
      }
      return <Text key={i} mb="2"><Inlines nodes={b.c} /></Text>;
    })}
  </Box>;
}

function missingText(kind, expected) {
  const p = expected?.[kind];
  if (kind === "day") {
    return "Yesterday's summary isn't in yet. It's usually posted by about 8:30 AM PT.";
  }
  const label = p ? MONTHS[Number(p.split("-")[1]) - 1] : "this month";
  return kind === "month_to_date"
    ? "No month-so-far summary for " + label + " yet."
    : "No summary for " + label + " yet.";
}

function RecapTabs({ value, onChange, fresh }) {
  const { getRootProps, getRadioProps } = useRadioGroup({ name: "recap-kind", value, onChange });
  return <Flex {...getRootProps()} gap="1.5" wrap="wrap" my="2" id="recap-tabs">
    {KINDS.map((k) => {
      const radio = getRadioProps({ value: k });
      return <RadioCard key={k} px={{ base: 2, md: 3 }} py="1" box={{ fontSize: "sm", opacity: fresh[k] ? 1 : 0.6 }} {...radio}>
        {TAB_NAMES[k]}
      </RadioCard>;
    })}
  </Flex>;
}

const CARD = {
  width: { base: "98%", md: "460px" }, minHeight: "250px", border: "2px solid #656382", bg: "gray.100",
  p: { base: 2, md: 4 }, my: 2, mx: { base: 0, md: 3 }, borderRadius: "10px",
};

export function RecapCard() {
  const { recap, error, loading } = useRecap();
  const fresh = Object.fromEntries(KINDS.map((k) => [k, !!(recap?.[k]?.fresh)]));
  const firstFresh = KINDS.find((k) => fresh[k]) || "day";
  const [kind, setKind] = useState(null);
  useEffect(() => { if (kind == null && recap) setKind(firstFresh); }, [recap, kind, firstFresh]);
  const active = kind || firstFresh;

  // Not set up on this server (table missing) or the API failed: no card at all.
  if (error || recap?.available === false) {
    return null;
  }
  const dayEntry = recap?.day;
  const isYesterday = fresh.day && dayEntry?.period === recap?.expected?.day;
  const title = isYesterday || !fresh.day ? "Yesterday in brief" : "In brief: " + periodLabel(dayEntry).split(",")[0];

  if (loading) {
    return <Box id="recap-card" {...CARD}>
      <Text fontSize={{ base: "lg", md: "xl" }}>Yesterday in brief</Text>
      <Spinner size="sm" mt="3" />
    </Box>;
  }
  if (!KINDS.some((k) => fresh[k])) {
    return <Box id="recap-card" className="recap-placeholder" {...CARD}>
      <Text fontSize={{ base: "lg", md: "xl" }}>Yesterday in brief</Text>
      <Text fontSize="sm" mt="3" color="gray.700">
        No recent summary yet. A short write-up of yesterday's weather, the month so far and last month
        appears here each morning, usually by about 8:30 AM PT.
      </Text>
      <Text fontSize="xs" color="gray.600" mt="3">
        Meanwhile, see the <Link href="/reports/day" textDecoration="underline">daily report</Link>.
      </Text>
    </Box>;
  }

  const entry = recap?.[active];
  const shown = entry && entry.fresh;
  return <Box id="recap-card" {...CARD}>
    <Text fontSize={{ base: "lg", md: "xl" }}>{title}</Text>
    <RecapTabs value={active} onChange={setKind} fresh={fresh} />
    {shown
      ? <Box className={"recap-entry recap-" + active}>
        <Text className="recap-period" fontSize="xs" fontWeight="bold" color="gray.600" textTransform="uppercase"
          letterSpacing="wide" mb="1">{periodLabel(entry)}</Text>
        <RecapBody blocks={entry.blocks} />
        <Text fontSize="xs" color="gray.600" mt="1">
          {active === "day" && <><Link href={"/reports/day?date=" + entry.period} textDecoration="underline">Daily report</Link> &middot; </>}
          Written {updatedLabel(entry.generated_at)}
        </Text>
      </Box>
      : <Text className="recap-missing" fontSize="sm" color="gray.700" mt="2">{missingText(active, recap?.expected)}</Text>}
  </Box>;
}
