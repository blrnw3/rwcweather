import useSWR from "swr";
import { fetcher } from "./conf";
import { LIVE_SWR, useLivePoll } from "./liveRefresh";

export function useFogDay(datestamp, refreshMs = 300000) {
    const key = datestamp ? "/api/fog/day/" + datestamp : null;
    const { data, error, revalidate } = useSWR(key, fetcher, LIVE_SWR);
    useLivePoll(key, revalidate, refreshMs, { minAgeMs: 15000 });
    if (error) {
        return { error: true };
    }
    return { fog: data?.result, now: data?.server?.epoch ? data.server.epoch * 1000 : null };
}
