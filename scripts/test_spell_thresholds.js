#!/usr/bin/env node
// Run with: node scripts/test_spell_thresholds.js
"use strict";

const fs = require("fs");
const path = require("path");
const assert = require("assert");

const root = path.resolve(__dirname, "..");
const reportSrc = fs.readFileSync(path.join(root, "web/app/components/report.js"), "utf8");
const spellsSrc = fs.readFileSync(path.join(root, "web/app/components/spells.js"), "utf8");

const mmToIn = (mm) => String(Math.round(mm / 25.4 * 10000) / 10000);
function nearestThreshold(value, options) {
    if (!options.length || options.includes(value)) {
        return value;
    }
    return options.reduce((best, o) => Math.abs(Number(o) - Number(value)) < Math.abs(Number(best) - Number(value)) ? o : best);
}

// Keep this file's helpers aligned with report.js.
assert.ok(reportSrc.includes("export const mmToIn = (mm) => String(Math.round(mm / 25.4 * 10000) / 10000);"));
assert.ok(reportSrc.includes("if (!options.length || options.includes(value))"));

const metricMatch = spellsSrc.match(/rain: \{ total: \["0\.01", \.\.\.\[([^\]]+)\]\.map\(mmToIn\)\] \}/);
assert.ok(metricMatch, "SPELL_CONF_METRIC rain totals list not found");
const metricMm = metricMatch[1].split(",").map((s) => Number(s.trim()));
assert.deepStrictEqual(metricMm, [1, 2.5, 5, 10, 25]);
assert.ok(!metricMm.includes(2), "2 mm should no longer be a displayed rain-total option");

const metricOptions = ["0.01", ...metricMm.map(mmToIn)];
assert.deepStrictEqual(metricOptions, ["0.01", "0.0394", "0.0984", "0.1969", "0.3937", "0.9843"]);

// Older links that used 2 mm are accepted, then mapped to 2.5 mm in a metric view.
assert.ok(spellsSrc.includes("mmToIn(2)"), "spellThresholdsAny should still accept 2 mm");
assert.strictEqual(nearestThreshold(mmToIn(2), metricOptions), mmToIn(2.5));
assert.strictEqual(mmToIn(2), "0.0787");
assert.strictEqual(mmToIn(2.5), "0.0984");

// Metric labels: 1 dp in mm, trailing .0 stripped, so 1 mm and 2.5 mm display cleanly.
const asMm1 = Math.round(Number(mmToIn(1)) * 25.4 * 10) / 10;
const asMm25 = Math.round(Number(mmToIn(2.5)) * 25.4 * 10) / 10;
assert.strictEqual(asMm1, 1);
assert.strictEqual(asMm25, 2.5);

// Count-of-days rain thresholds are unchanged (not part of this spells change).
const countMatch = reportSrc.match(/rain: \["0", "0\.01", \.\.\.\[([^\]]+)\]\.map\(mmToIn\)\]/);
assert.ok(countMatch, "COUNT_THRESHOLDS_METRIC rain list not found");
assert.deepStrictEqual(countMatch[1].split(",").map((s) => Number(s.trim())), [2, 5, 10, 25]);

console.log("test_spell_thresholds.js: ok");
