#!/usr/bin/env node
// Run with: node scripts/test_month_normal_to_date.js
// Exercises monthlyNormalToDate / waterYearNormalToDate / waterYearDateForTotal from climate.js
// against the published rain normals, without a JS test runner.

"use strict";

const fs = require("fs");
const path = require("path");
const assert = require("assert");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const climateSrc = fs.readFileSync(path.join(root, "web/app/components/climate.js"), "utf8");
const dataSrc = fs.readFileSync(path.join(root, "web/app/data/climate.js"), "utf8");

function extractExportConst(src, name) {
    const start = src.indexOf("export const " + name);
    if (start < 0) throw new Error("missing export " + name);
    const assign = src.indexOf("=", start);
    let i = assign + 1;
    while (src[i] && /\s/.test(src[i])) i++;
    if (src[i] !== "{") throw new Error(name + " is not an object literal");
    let depth = 0;
    const from = i;
    for (; i < src.length; i++) {
        if (src[i] === "{") depth++;
        else if (src[i] === "}") {
            depth--;
            if (depth === 0) return src.slice(from, i + 1);
        }
    }
    throw new Error("unclosed object for " + name);
}

function extractFunction(src, name) {
    const re = new RegExp("(?:export )?function " + name + "\\(");
    const m = re.exec(src);
    if (!m) throw new Error("missing function " + name);
    let start = src.indexOf("function " + name + "(", m.index);
    if (start < 0) throw new Error("function keyword missing for " + name);
    let i = src.indexOf("{", start);
    let depth = 0;
    for (; i < src.length; i++) {
        if (src[i] === "{") depth++;
        else if (src[i] === "}") {
            depth--;
            if (depth === 0) return src.slice(start, i + 1);
        }
    }
    throw new Error("unclosed function " + name);
}

const CLIMATE_NORMALS = vm.runInNewContext("(" + extractExportConst(dataSrc, "CLIMATE_NORMALS") + ")");
const monthly = CLIMATE_NORMALS.normals.rain.total.monthly;
assert.strictEqual(monthly.length, 12);
assert.strictEqual(monthly[10], 2.29); // November
assert.strictEqual(monthly[9], 1.02);  // October

const sandbox = {
    CLIMATE_NORMALS,
    module: { exports: {} },
    exports: {},
};
const harness = [
    "function isTotal(stat) { return stat === 'total'; }",
    "function mean(values) { return values.reduce((a, b) => a + b, 0) / values.length; }",
    "const MONTHLY_KEYS = Array.from(Array(12).keys());",
    extractFunction(climateSrc, "normalsFor"),
    extractFunction(climateSrc, "hasClimate"),
    extractFunction(climateSrc, "daysInMonth"),
    "const WATER_YEAR_FIRST_MONTH = 10;",
    extractFunction(climateSrc, "monthlyNormalToDate"),
    extractFunction(climateSrc, "waterYearNormalToDate"),
    extractFunction(climateSrc, "dailyNormal"),
    extractFunction(climateSrc, "periodToDateTotalNormal"),
    extractFunction(climateSrc, "waterYearDateForTotal"),
    "this.monthlyNormalToDate = monthlyNormalToDate;",
    "this.waterYearNormalToDate = waterYearNormalToDate;",
    "this.periodToDateTotalNormal = periodToDateTotalNormal;",
    "this.waterYearDateForTotal = waterYearDateForTotal;",
    "this.daysInMonth = daysInMonth;",
].join("\n;\n");
vm.runInNewContext(harness, sandbox);

const { monthlyNormalToDate, waterYearNormalToDate, periodToDateTotalNormal, waterYearDateForTotal, daysInMonth } = sandbox;

function almost(a, b, msg) {
    assert.ok(Math.abs(a - b) < 1e-12, (msg || "") + " " + a + " !== " + b);
}

// Pro-rata: November 2026 (30 days), 16th
almost(daysInMonth(2026, 11), 30);
const novToDate = monthlyNormalToDate("rain", "total", 2026, 11, 16);
almost(novToDate, 2.29 * 16 / 30, "Nov 16 to-date");

// Last day of the month equals the full-month normal
almost(monthlyNormalToDate("rain", "total", 2026, 11, 30), 2.29, "Nov 30");

// Leap February
almost(daysInMonth(2024, 2), 29);
almost(monthlyNormalToDate("rain", "total", 2024, 2, 29), monthly[1], "Feb 29 leap");
almost(monthlyNormalToDate("rain", "total", 2025, 2, 28), monthly[1], "Feb 28 non-leap");
almost(monthlyNormalToDate("rain", "total", 2025, 2, 14), monthly[1] * 14 / 28, "Feb 14 non-leap");

// Non-totals and unknown vars have no to-date normal
assert.strictEqual(monthlyNormalToDate("rain", "avg", 2026, 11, 16), null);
assert.strictEqual(monthlyNormalToDate("wind", "total", 2026, 11, 16), null);
assert.strictEqual(waterYearNormalToDate("rain", "avg", 2026, 11, 16), null);

// Water year reuses the same current-month pro-rata
const wy = waterYearNormalToDate("rain", "total", 2026, 11, 16);
almost(wy, monthly[9] + novToDate, "WY Nov 16 = Oct + Nov to date");
almost(waterYearNormalToDate("rain", "total", 2026, 10, 1), monthly[9] * 1 / 31, "WY Oct 1");
const fullWy = monthly.slice(9).concat(monthly.slice(0, 9)).reduce((a, b) => a + b, 0);
almost(waterYearNormalToDate("rain", "total", 2026, 9, 30), fullWy, "WY Sep 30 full");

// periodToDateTotalNormal (used on the This month card) matches month to date
almost(periodToDateTotalNormal("rain", 2026, 11, 1, 2026, 11, 16), novToDate, "periodToDate == monthlyToDate");

// Percent of normal as shown on the card (ClimateAnom rounding)
function pct(value, normal) {
    return Math.round((value / normal) * 100);
}
const monthRain = 2.13;
assert.strictEqual(pct(monthRain, 2.29), 93, "old full-month %");
assert.strictEqual(pct(monthRain, novToDate), 174, "new to-date %");

// Tiny expected normal is treated as absent on the card (>= 0.005 gate)
assert.ok(monthlyNormalToDate("rain", "total", 2026, 7, 1) < 0.005 || monthly[6] * 1 / 31 < 0.005, "July 1 expected may be under gate");

// waterYearDateForTotal: date whose cumulative normal first reaches the current total
function wyDate(year, month, day, total) {
    return waterYearDateForTotal("rain", "total", year, month, day, total);
}
// Values come from a vm sandbox, so compare a plain JSON clone.
function sameDate(actual, expected, msg) {
    assert.deepStrictEqual(actual == null ? actual : JSON.parse(JSON.stringify(actual)), expected, msg);
}
sameDate(wyDate(2026, 11, 18, 0), { month: 10, day: 1 }, "zero total is 1 Oct");
assert.strictEqual(wyDate(2026, 11, 18, null), null);
assert.strictEqual(wyDate(2026, 11, 18, -0.1), null);
assert.strictEqual(waterYearDateForTotal("rain", "avg", 2026, 11, 18, 1), null);

const t14dec = waterYearNormalToDate("rain", "total", 2026, 12, 14);
sameDate(wyDate(2026, 11, 18, t14dec), { month: 12, day: 14 }, "exact Dec 14 normal");
const t13dec = waterYearNormalToDate("rain", "total", 2026, 12, 13);
sameDate(wyDate(2026, 11, 18, t13dec), { month: 12, day: 13 }, "exact Dec 13 normal");
sameDate(wyDate(2026, 11, 18, (t13dec + t14dec) / 2), { month: 12, day: 14 }, "between Dec 13 and 14");

// Mid-October (past relative to mid-November) and April (future, next calendar year of the WY)
const t15oct = waterYearNormalToDate("rain", "total", 2026, 10, 15);
sameDate(wyDate(2026, 11, 18, t15oct), { month: 10, day: 15 }, "past date in the water year");
const t3apr = waterYearNormalToDate("rain", "total", 2027, 4, 3);
sameDate(wyDate(2026, 11, 18, t3apr), { month: 4, day: 3 }, "future date later in the water year");

sameDate(wyDate(2026, 11, 18, fullWy), { month: 9, day: 30 }, "exact full-year normal is 30 Sep");
sameDate(wyDate(2026, 11, 18, fullWy + 0.01), { exceeds: true }, "above the annual normal");
sameDate(wyDate(2026, 9, 30, fullWy), { month: 9, day: 30 }, "Sep date still uses that water year");

// First day of the water year: any positive total up to Oct 1's normal lands on 1 Oct
const t1oct = waterYearNormalToDate("rain", "total", 2026, 10, 1);
sameDate(wyDate(2026, 11, 18, t1oct), { month: 10, day: 1 }, "Oct 1 end-of-day normal");
sameDate(wyDate(2026, 11, 18, t1oct / 2), { month: 10, day: 1 }, "below Oct 1 normal");

// Leap-year February in the 2023-24 water year (today in Mar 2024)
assert.strictEqual(daysInMonth(2024, 2), 29);
const t29feb = waterYearNormalToDate("rain", "total", 2024, 2, 29);
sameDate(wyDate(2024, 3, 1, t29feb), { month: 2, day: 29 }, "leap Feb 29");
const t28feb = waterYearNormalToDate("rain", "total", 2024, 2, 28);
sameDate(wyDate(2024, 3, 1, t28feb), { month: 2, day: 28 }, "leap Feb 28");
// Non-leap WY 2024-25: 28 Feb is the last day of February
assert.strictEqual(daysInMonth(2025, 2), 28);
const t28feb25 = waterYearNormalToDate("rain", "total", 2025, 2, 28);
sameDate(wyDate(2025, 3, 1, t28feb25), { month: 2, day: 28 }, "non-leap Feb 28");

console.log("ok: monthlyNormalToDate / waterYearNormalToDate / waterYearDateForTotal (" +
    "Nov 16 2026 to-date " + novToDate.toFixed(4) + " in, " +
    "month 2.13 in -> " + pct(monthRain, novToDate) + "% vs " + pct(monthRain, 2.29) + "% full month, " +
    "14 Dec normal maps back to 14 Dec)");
