import { useEffect, useRef } from "react";

// Polling for live views that refreshes as soon as the page is seen again.
//
// Phones suspend background tabs, so a plain interval (or SWR's refreshInterval) leaves stale numbers on screen
// until its next tick after the tab comes back, and a request that was in flight when the tab was suspended can
// hold SWR's deduped revalidation hostage for seconds. Here:
//   * the page counts as "viewed" on visibilitychange -> visible, pageshow (bfcache restores, e.g. iOS Safari back
//     or tab switches) and window focus; events within VIEW_DEBOUNCE_MS of each other count once;
//   * on view, each live poller refreshes at once (a fresh request, not deduped onto a stuck one) unless its data
//     was requested within minAgeMs, and its regular timer restarts from that refresh;
//   * timers are paused while the page is hidden (no requests from background tabs);
//   * the time of the last request is shared per key, so two pollers of one endpoint (e.g. the home page and the
//     header strip both use /api/web/dashboard/live) never double-fetch.

export const VIEW_DEBOUNCE_MS = 1000;
export const MIN_AGE_MS = 2500;

const viewListeners = new Set();
const hideListeners = new Set();
const lastRequest = new Map();     // key -> ms of the last request started
let lastView = 0;
let installed = false;

function isHidden() {
    return typeof document !== "undefined" && document.visibilityState === "hidden";
}

function fireView() {
    if (isHidden()) {
        return;
    }
    const now = Date.now();
    if (now - lastView < VIEW_DEBOUNCE_MS) {
        return;
    }
    lastView = now;
    for (const fn of Array.from(viewListeners)) {
        fn();
    }
}

function install() {
    if (installed || typeof window === "undefined") {
        return;
    }
    installed = true;
    document.addEventListener("visibilitychange", () => {
        if (isHidden()) {
            for (const fn of Array.from(hideListeners)) {
                fn();
            }
        } else {
            fireView();
        }
    });
    window.addEventListener("pageshow", (e) => { if (e.persisted) fireView(); });
    window.addEventListener("focus", fireView);
}

// Call `refresh` every intervalMs while the page is visible, and right away when it is viewed again.
// `refresh` should start a new request (for SWR, the hook's own `revalidate`, which is not deduped).
// The first request is the caller's own (e.g. SWR's on mount), so the timer starts from mount.
export function useLivePoll(key, refresh, intervalMs, { minAgeMs = MIN_AGE_MS, enabled = true } = {}) {
    const refreshRef = useRef(refresh);
    refreshRef.current = refresh;
    const intervalRef = useRef(intervalMs);
    intervalRef.current = intervalMs;

    useEffect(() => {
        if (!enabled || !key || !intervalMs) {
            return undefined;
        }
        install();
        let timer = null;
        if (!lastRequest.has(key)) {
            lastRequest.set(key, Date.now());
        }
        const schedule = () => {
            clearTimeout(timer);
            timer = isHidden() ? null : setTimeout(tick, intervalRef.current);
        };
        const run = () => {
            lastRequest.set(key, Date.now());
            try {
                refreshRef.current();
            } catch (e) {
                console.log(e);
            }
        };
        function tick() {
            // another poller of the same key may have refreshed meanwhile
            const age = Date.now() - (lastRequest.get(key) || 0);
            if (age >= Math.min(minAgeMs, intervalRef.current)) {
                run();
            }
            schedule();
        }
        const onView = () => {
            if (Date.now() - (lastRequest.get(key) || 0) >= minAgeMs) {
                run();
                schedule();         // regular timer restarts from this refresh
            } else if (!timer) {
                schedule();         // fresh enough; just resume the timer if it was paused
            }
        };
        const onHide = () => { clearTimeout(timer); timer = null; };
        viewListeners.add(onView);
        hideListeners.add(onHide);
        schedule();
        return () => {
            clearTimeout(timer);
            viewListeners.delete(onView);
            hideListeners.delete(onHide);
        };
    }, [key, enabled, !intervalMs, minAgeMs]); // eslint-disable-line react-hooks/exhaustive-deps
}

// SWR options for data polled by useLivePoll: it owns the timer and the focus/visibility refresh.
export const LIVE_SWR = { refreshInterval: 0, revalidateOnFocus: false };
