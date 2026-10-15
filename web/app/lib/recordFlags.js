// Today-vs-record status for the home climate/records card.
// Mirrors rwcwx/calc/record_flags.py.

export const RECORD = "record";
export const TIE = "tie";
export const ON_TRACK = "on_track";

const MORNING_MIN_DONE_HOUR = 10; // local: overnight low treated as final
const EVENING_MAX_DONE_HOUR = 18; // local: daytime high treated as final

function cmpBreak(today, record, wantAbove) {
    if (today == null || record == null || Number.isNaN(today) || Number.isNaN(record)) return null;
    if (wantAbove) {
        if (today > record) return RECORD;
        if (today === record) return TIE;
        return null;
    }
    if (today < record) return RECORD;
    if (today === record) return TIE;
    return null;
}

/** Hottest high — final as soon as exceeded. */
export function hottestHigh(todayMax, recordMax) {
    return cmpBreak(todayMax, recordMax, true);
}

/** Coldest low — final as soon as exceeded. */
export function coldestLow(todayMin, recordMin) {
    return cmpBreak(todayMin, recordMin, false);
}

/** Warmest low — on_track until ~10:00 local, then record/tie. */
export function warmestLow(todayMin, recordWarmMin, localHour, morningDone) {
    if (todayMin == null || recordWarmMin == null) return null;
    if (todayMin < recordWarmMin) return null;
    const confirmed = morningDone != null ? morningDone : localHour >= MORNING_MIN_DONE_HOUR;
    if (!confirmed) return ON_TRACK;
    return todayMin > recordWarmMin ? RECORD : TIE;
}

/** Coldest high — on_track until ~18:00 local, then record/tie. */
export function coldestHigh(todayMax, recordColdMax, localHour, eveningDone) {
    if (todayMax == null || recordColdMax == null) return null;
    if (todayMax > recordColdMax) return null;
    const confirmed = eveningDone != null ? eveningDone : localHour >= EVENING_MAX_DONE_HOUR;
    if (!confirmed) return ON_TRACK;
    return todayMax < recordColdMax ? RECORD : TIE;
}

export function localHourFromServer(summaryOrDash) {
    const local = summaryOrDash?.server?.localtime;
    if (local && local.length >= 13) {
        const h = Number(local.slice(11, 13));
        if (!Number.isNaN(h)) return h;
    }
    return new Date().getHours();
}
