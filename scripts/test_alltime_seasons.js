#!/usr/bin/env node
// Run with: node scripts/test_alltime_seasons.js
"use strict";

const fs = require("fs");
const path = require("path");
const assert = require("assert");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const src = fs.readFileSync(path.join(root, "web/app/components/seasons.js"), "utf8");
const load = new Function(src.replace(/export /g, "") +
    "; return { SEASONS, SEASON_LABELS, PERIODS, PERIOD_LABELS, seasonOf, seasonIndex, isSeasonCurrentOrFuture, isSeasonFuture, seasonMonths };");
const {
    SEASONS, SEASON_LABELS, PERIODS, PERIOD_LABELS,
    seasonOf, seasonIndex, isSeasonCurrentOrFuture, isSeasonFuture, seasonMonths,
} = load();

assert.deepStrictEqual(SEASONS, ["winter", "spring", "summer", "autumn"]);
assert.strictEqual(SEASON_LABELS.autumn, "Autumn");
assert.deepStrictEqual(PERIODS, ["monthly", "seasonal"]);
assert.strictEqual(PERIOD_LABELS.seasonal, "Seasonal");

// Winter is labelled by the year of January; December belongs to the next year.
assert.deepStrictEqual(seasonOf(2023, 11), { year: 2024, season: "winter" }); // Dec
assert.deepStrictEqual(seasonOf(2024, 0), { year: 2024, season: "winter" }); // Jan
assert.deepStrictEqual(seasonOf(2024, 1), { year: 2024, season: "winter" }); // Feb
assert.deepStrictEqual(seasonOf(2024, 2), { year: 2024, season: "spring" });
assert.deepStrictEqual(seasonOf(2024, 5), { year: 2024, season: "summer" });
assert.deepStrictEqual(seasonOf(2024, 8), { year: 2024, season: "autumn" });
assert.deepStrictEqual(seasonOf(2024, 10), { year: 2024, season: "autumn" }); // Nov

assert.deepStrictEqual(seasonMonths("winter"), [12, 1, 2]);
assert.strictEqual(seasonIndex("summer"), 2);

// Today 21 Nov 2026: Autumn 2026 is current (shown, excluded from stats);
// Winter 2027 has not started (future, blank).
assert.strictEqual(isSeasonCurrentOrFuture(2026, "autumn", 2026, 10), true);
assert.strictEqual(isSeasonFuture(2026, "autumn", 2026, 10), false);
assert.strictEqual(isSeasonCurrentOrFuture(2026, "summer", 2026, 10), false);
assert.strictEqual(isSeasonFuture(2026, "summer", 2026, 10), false);
assert.strictEqual(isSeasonCurrentOrFuture(2027, "winter", 2026, 10), true);
assert.strictEqual(isSeasonFuture(2027, "winter", 2026, 10), true);
assert.strictEqual(isSeasonCurrentOrFuture(2026, "winter", 2026, 10), false);

// Today 15 Jan 2027: Winter 2027 is current; Autumn 2026 is complete.
assert.strictEqual(isSeasonCurrentOrFuture(2027, "winter", 2027, 0), true);
assert.strictEqual(isSeasonFuture(2027, "winter", 2027, 0), false);
assert.strictEqual(isSeasonCurrentOrFuture(2026, "autumn", 2027, 0), false);
assert.strictEqual(isSeasonFuture(2027, "spring", 2027, 0), true);

// URL: period=seasonal is a distinct shareable value; monthly is the default.
function resolvePeriod(query) {
    const allowed = PERIODS;
    const value = query && query.period;
    return allowed.includes(value) ? value : "monthly";
}
function urlFor(period) {
    return period === "monthly" ? "" : "period=" + period;
}
assert.strictEqual(resolvePeriod({}), "monthly");
assert.strictEqual(resolvePeriod({ period: "seasonal" }), "seasonal");
assert.strictEqual(resolvePeriod({ period: "weekly" }), "monthly");
assert.strictEqual(urlFor("monthly"), "");
assert.strictEqual(urlFor("seasonal"), "period=seasonal");

console.log("test_alltime_seasons.js: all assertions passed");
