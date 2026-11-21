// Meteorological seasons for the all-time report seasonal grid.
// Winter is Dec–Feb, labelled by the year that contains January
// (Dec 2023 belongs to Winter 2024). Autumn is Sep–Nov (Fall).

export const SEASONS = ["winter", "spring", "summer", "autumn"];

export const SEASON_LABELS = {
    winter: "Winter",
    spring: "Spring",
    summer: "Summer",
    autumn: "Autumn",
};

const SEASON_MONTHS = {
    winter: [12, 1, 2],
    spring: [3, 4, 5],
    summer: [6, 7, 8],
    autumn: [9, 10, 11],
};

/** Calendar year + 0-based month → { year, season }. December is the next year's winter. */
export function seasonOf(year, monthIdx) {
    if (monthIdx === 11) {
        return { year: year + 1, season: "winter" };
    }
    if (monthIdx <= 1) {
        return { year, season: "winter" };
    }
    if (monthIdx <= 4) {
        return { year, season: "spring" };
    }
    if (monthIdx <= 7) {
        return { year, season: "summer" };
    }
    return { year, season: "autumn" };
}

export function seasonIndex(season) {
    return SEASONS.indexOf(season);
}

/**
 * True if this labelled season is the current in-progress one or a future season
 * relative to `currentYear` / `currentMonthIdx` (0-based), matching how the
 * monthly grid treats the current month and later months of this year.
 */
export function isSeasonCurrentOrFuture(year, season, currentYear, currentMonthIdx) {
    const current = seasonOf(currentYear, currentMonthIdx);
    if (year !== current.year) {
        return year > current.year;
    }
    return seasonIndex(season) >= seasonIndex(current.season);
}

/** True if this labelled season has not started yet (the current season is shown, like the current month). */
export function isSeasonFuture(year, season, currentYear, currentMonthIdx) {
    const current = seasonOf(currentYear, currentMonthIdx);
    if (year !== current.year) {
        return year > current.year;
    }
    return seasonIndex(season) > seasonIndex(current.season);
}

/** Months (1-12) that make up a season; Winter is Dec, Jan, Feb. */
export function seasonMonths(season) {
    return SEASON_MONTHS[season] || [];
}

export const PERIODS = ["monthly", "seasonal"];

export const PERIOD_LABELS = {
    monthly: "Monthly",
    seasonal: "Seasonal",
};
