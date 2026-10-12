import { Box, Flex, Text, Tooltip } from "@chakra-ui/react";
import useSWR from "swr";
import { fetcher } from "./conf";

// Webcam sunshine: minute-level ribbon from sunrise to sunset, and the day's data hook.
// Spells come from /api/sun/day/<YYYYMMDD> as [start, end) epoch ms with state sun | nosun | unknown.

const COLOURS = {
    sun: "#f6c445",
    nosun: "#9aa3ad",
    unknown: "repeating-linear-gradient(45deg, #e2e8f0, #e2e8f0 4px, #cbd5e0 4px, #cbd5e0 8px)",
    future: "#edf2f7",
};
const LABELS = { sun: "Sunny", nosun: "Not sunny", unknown: "No data", future: "Not yet" };

const timeFmt = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Los_Angeles" });
export const fmtTime = (ms) => timeFmt.format(new Date(ms));

export function useSunDay(datestamp, refreshMs = 300000) {
    const { data, error } = useSWR("/api/sun/day/" + (datestamp || ""), fetcher, { refreshInterval: refreshMs });
    if (error) {
        return { error: true };
    }
    return { day: data?.result, now: data?.server?.epoch ? data.server.epoch * 1000 : null };
}

// Fill [sunrise, sunset] with the spells, padding gaps as "unknown" (past) or "future".
export function ribbonSegments(day, nowMs) {
    if (!day) {
        return [];
    }
    const { sunrise, sunset } = day;
    const end = nowMs ? Math.min(Math.max(nowMs, sunrise), sunset) : sunset;
    const segs = [];
    let t = sunrise;
    for (const s of day.spells || []) {
        const a = Math.max(s.start, sunrise), b = Math.min(s.end, sunset);
        if (b <= a) {
            continue;
        }
        if (a > t) {
            segs.push({ start: t, end: a, state: a <= end ? "unknown" : "future" });
        }
        segs.push({ start: a, end: b, state: s.state });
        t = b;
    }
    if (t < end) {
        segs.push({ start: t, end: end, state: "unknown" });
        t = end;
    }
    if (t < sunset) {
        segs.push({ start: t, end: sunset, state: "future" });
    }
    return segs;
}

export function SunRibbon({ day, nowMs, height = "18px", showLabels = true }) {
    if (!day) {
        return <Box h={height} bg={COLOURS.future} borderRadius="4" />;
    }
    const span = day.sunset - day.sunrise;
    const segs = ribbonSegments(day, nowMs);
    return <Box className="sun-ribbon">
        <Flex h={height} borderRadius="4" overflow="hidden" border="1px solid #cbd5e0">
            {segs.map((s, i) =>
                <Tooltip key={i} label={LABELS[s.state] + ": " + fmtTime(s.start) + " – " + fmtTime(s.end)}>
                    <Box flexGrow={(s.end - s.start) / span} flexShrink="0" flexBasis="0" background={COLOURS[s.state]}
                        data-state={s.state} />
                </Tooltip>
            )}
        </Flex>
        {showLabels && <Flex justify="space-between" fontSize="xs" color="gray.600">
            <Text>↑ {fmtTime(day.sunrise)}</Text>
            <Text>{fmtTime(day.sunset)} ↓</Text>
        </Flex>}
    </Box>;
}

export function SunLegend() {
    return <Flex gap="3" fontSize="xs" color="gray.600" wrap="wrap">
        {["sun", "nosun", "unknown"].map((k) => <Flex key={k} align="center" gap="1">
            <Box w="12px" h="12px" background={COLOURS[k]} border="1px solid #cbd5e0" />{LABELS[k]}
        </Flex>)}
    </Flex>;
}
