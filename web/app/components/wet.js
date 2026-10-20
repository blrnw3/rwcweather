import { Box, Flex, Text, Tooltip } from "@chakra-ui/react";
import useSWR from "swr";
import { fetcher } from "./conf";
import { LIVE_SWR, useLivePoll } from "./liveRefresh";
import { fmtTime } from "./sun";

// Today's wet spells on a midnight-to-midnight bar, styled like the sunshine ribbon (SunRibbon).
// wet = /api/web/dashboard/live "wet" block: day_start / day_end and spell_list [start, end) as epoch ms.
const COLOURS = { wet: "#3182ce", dry: "#e2e8f0", future: "#f7fafc" };
const LABELS = { wet: "Wet", dry: "Dry", future: "Not yet" };

export function wetSegments(wet, nowMs) {
    const { day_start: st, day_end: en } = wet;
    const end = nowMs ? Math.min(Math.max(nowMs, st), en) : en;
    const segs = [];
    let t = st;
    for (const s of wet.spell_list || []) {
        const a = Math.max(s.start, st), b = Math.min(s.end, en);
        if (b <= a) {
            continue;
        }
        if (a > t) {
            segs.push({ start: t, end: a, state: "dry" });
        }
        segs.push({ start: a, end: b, state: "wet" });
        t = b;
    }
    if (t < end) {
        segs.push({ start: t, end: end, state: "dry" });
        t = end;
    }
    if (t < en) {
        segs.push({ start: t, end: en, state: "future" });
    }
    return segs;
}

export function WetRibbon({ wet, nowMs, height = "16px" }) {
    if (!wet?.day_start || !wet?.day_end) {
        return null;
    }
    const span = wet.day_end - wet.day_start;
    const ticks = [6, 12, 18].map((h) => ({ h, f: (h * 3600000) / span }));
    return <Box className="wet-ribbon">
        <Flex h={height} borderRadius="4" overflow="hidden" border="1px solid #cbd5e0">
            {wetSegments(wet, nowMs).map((s, i) =>
                <Tooltip key={i} label={LABELS[s.state] + ": " + fmtTime(s.start) + " – " + fmtTime(s.end)}>
                    <Box flexGrow={(s.end - s.start) / span} flexShrink="0" flexBasis="0" background={COLOURS[s.state]}
                        data-state={s.state} />
                </Tooltip>)}
        </Flex>
        <Box position="relative" h="14px" fontSize="xs" color="gray.600">
            <Text position="absolute" left="0">00</Text>
            {ticks.map(({ h, f }) => <Text key={h} position="absolute" left={(f * 100) + "%"} transform="translateX(-50%)">{h}</Text>)}
            <Text position="absolute" right="0">24</Text>
        </Box>
    </Box>;
}

// Stored wet minutes (obs.wet) for one local day: /api/wet/day/<YYYYMMDD>, same shape as the dashboard block.
export function useWetDay(datestamp, refreshMs = 300000) {
    const key = datestamp ? "/api/wet/day/" + datestamp : null;
    const { data, error, revalidate } = useSWR(key, fetcher, LIVE_SWR);
    useLivePoll(key, revalidate, refreshMs, { minAgeMs: 15000 });
    if (error) {
        return { error: true };
    }
    return { wet: data?.result, now: data?.server?.epoch ? data.server.epoch * 1000 : null };
}

export function WetLegend() {
    return <Flex gap="3" fontSize="xs" color="gray.600" wrap="wrap">
        {["wet", "dry"].map((k) => <Flex key={k} align="center" gap="1">
            <Box w="12px" h="12px" background={COLOURS[k]} border="1px solid #cbd5e0" />{LABELS[k]}
        </Flex>)}
    </Flex>;
}
