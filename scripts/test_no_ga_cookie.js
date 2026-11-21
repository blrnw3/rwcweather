#!/usr/bin/env node
// Run with: node scripts/test_no_ga_cookie.js
"use strict";

const fs = require("fs");
const path = require("path");
const assert = require("assert");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const src = fs.readFileSync(path.join(root, "web/app/lib/ga.js"), "utf8");
const load = new Function(
    src.replace(/export /g, "") +
    "; return { GA_MEASUREMENT_ID, NO_GA_COOKIE, NO_GA_COOKIE_VALUE, NO_GA_MAX_AGE, " +
    "isNoTrackPath, cookieHasOptOut, isHttpsRequest, serializeOptOutCookie, " +
    "shouldSendGa, gaBootstrapInline };"
);
const {
    GA_MEASUREMENT_ID, NO_GA_COOKIE, NO_GA_COOKIE_VALUE, NO_GA_MAX_AGE,
    isNoTrackPath, cookieHasOptOut, isHttpsRequest, serializeOptOutCookie,
    shouldSendGa, gaBootstrapInline,
} = load();

assert.strictEqual(NO_GA_COOKIE, "rwc_no_ga");
assert.strictEqual(NO_GA_COOKIE_VALUE, "1");
assert.strictEqual(NO_GA_MAX_AGE, 10 * 365 * 24 * 60 * 60);
assert.ok(NO_GA_MAX_AGE >= 10 * 365 * 24 * 60 * 60);
assert.strictEqual(GA_MEASUREMENT_ID, "G-57NHWG35P0");

assert.strictEqual(isNoTrackPath("/no-track"), true);
assert.strictEqual(isNoTrackPath("/no-track/"), true);
assert.strictEqual(isNoTrackPath("/no-track?off=1"), true);
assert.strictEqual(isNoTrackPath("/"), false);
assert.strictEqual(isNoTrackPath("/about"), false);
assert.strictEqual(isNoTrackPath("/no-track-more"), false);

assert.strictEqual(cookieHasOptOut(""), false);
assert.strictEqual(cookieHasOptOut(null), false);
assert.strictEqual(cookieHasOptOut("rwc_no_ga=1"), true);
assert.strictEqual(cookieHasOptOut("rwc_no_ga=1; other=2"), true);
assert.strictEqual(cookieHasOptOut("other=2; rwc_no_ga=1"), true);
assert.strictEqual(cookieHasOptOut(" other=2 ; rwc_no_ga=1 ; x=y"), true);
assert.strictEqual(cookieHasOptOut('other=2; rwc_no_ga="1"'), true);
assert.strictEqual(cookieHasOptOut("rwc_no_ga=0"), false);
assert.strictEqual(cookieHasOptOut("rwc_no_ga=10"), false);
assert.strictEqual(cookieHasOptOut("rwc_no_ga=1x"), false);
assert.strictEqual(cookieHasOptOut("not_rwc_no_ga=1"), false);
assert.strictEqual(cookieHasOptOut("rwc_no_ga_extra=1"), false);
assert.strictEqual(cookieHasOptOut("prefix_rwc_no_ga=1"), false);

const setCookie = serializeOptOutCookie({ clear: false, secure: false });
assert.ok(setCookie.startsWith("rwc_no_ga=1;"));
assert.ok(setCookie.includes("Max-Age=" + NO_GA_MAX_AGE));
assert.ok(setCookie.includes("Path=/"));
assert.ok(setCookie.includes("SameSite=Lax"));
assert.ok(!setCookie.includes("Secure"));
assert.ok(!/HttpOnly/i.test(setCookie));

const setSecure = serializeOptOutCookie({ clear: false, secure: true });
assert.ok(setSecure.includes("Secure"));
assert.ok(setSecure.includes("SameSite=Lax"));

const cleared = serializeOptOutCookie({ clear: true, secure: true });
assert.ok(cleared.startsWith("rwc_no_ga="));
assert.ok(!cleared.startsWith("rwc_no_ga=1"));
assert.ok(cleared.includes("Max-Age=0"));
assert.ok(/Expires=Thu, 01 Jan 1970/i.test(cleared));
assert.ok(cleared.includes("Path=/"));
assert.ok(cleared.includes("SameSite=Lax"));
assert.ok(cleared.includes("Secure"));

assert.strictEqual(isHttpsRequest({ headers: { "x-forwarded-proto": "https" } }), true);
assert.strictEqual(isHttpsRequest({ headers: { "x-forwarded-proto": "https, http" } }), true);
assert.strictEqual(isHttpsRequest({ headers: { "x-forwarded-proto": "http" } }), false);
assert.strictEqual(isHttpsRequest({ headers: {}, secure: true }), true);
assert.strictEqual(isHttpsRequest({ headers: {}, connection: { encrypted: true } }), true);
assert.strictEqual(isHttpsRequest({ headers: {} }), false);
assert.strictEqual(isHttpsRequest(null), false);

assert.strictEqual(shouldSendGa({ nodeEnv: "development", cookieHeader: "", pathname: "/" }), false);
assert.strictEqual(shouldSendGa({ nodeEnv: "test", cookieHeader: "", pathname: "/" }), false);
assert.strictEqual(shouldSendGa({ nodeEnv: "production", cookieHeader: "", pathname: "/" }), true);
assert.strictEqual(shouldSendGa({ nodeEnv: "production", cookieHeader: "rwc_no_ga=1", pathname: "/" }), false);
assert.strictEqual(shouldSendGa({ nodeEnv: "production", cookieHeader: "", pathname: "/no-track" }), false);
assert.strictEqual(shouldSendGa({ nodeEnv: "production", cookieHeader: "", pathname: "/about" }), true);

function runBootstrap({ cookie, pathname }) {
    const appended = [];
    const document = {
        cookie: cookie || "",
        createElement: function (tag) {
            return { tagName: tag, async: false, src: "" };
        },
        head: {
            appendChild: function (el) { appended.push(el); },
        },
    };
    const window = {
        document: document,
        location: { pathname: pathname || "/" },
        dataLayer: undefined,
        gtag: undefined,
    };
    vm.runInNewContext(gaBootstrapInline(), { window: window, document: document, Date: Date });
    return { window: window, appended: appended };
}

const gtagSrc = "https://www.googletagmanager.com/gtag/js?id=" + GA_MEASUREMENT_ID;

const loaded = runBootstrap({ cookie: "", pathname: "/" });
assert.strictEqual(loaded.appended.length, 1);
assert.strictEqual(loaded.appended[0].src, gtagSrc);
assert.strictEqual(loaded.appended[0].async, true);
assert.strictEqual(typeof loaded.window.gtag, "function");
assert.ok(Array.isArray(loaded.window.dataLayer));
assert.ok(loaded.window.dataLayer.length >= 2);
assert.ok(!loaded.window["ga-disable-" + GA_MEASUREMENT_ID]);

const opted = runBootstrap({ cookie: "other=1; rwc_no_ga=1", pathname: "/" });
assert.strictEqual(opted.appended.length, 0);
assert.strictEqual(opted.window["ga-disable-" + GA_MEASUREMENT_ID], true);
assert.strictEqual(typeof opted.window.gtag, "undefined");

const noTrack = runBootstrap({ cookie: "", pathname: "/no-track" });
assert.strictEqual(noTrack.appended.length, 0);
assert.strictEqual(noTrack.window["ga-disable-" + GA_MEASUREMENT_ID], true);

const noTrackOff = runBootstrap({ cookie: "", pathname: "/no-track" });
assert.strictEqual(noTrackOff.appended.length, 0);

const substring = runBootstrap({ cookie: "prefix_rwc_no_ga=1; rwc_no_ga=10", pathname: "/forecast" });
assert.strictEqual(substring.appended.length, 1);

// Dev gate: _document only emits the bootstrap when NODE_ENV is production.
const documentSrc = fs.readFileSync(path.join(root, "web/app/pages/_document.js"), "utf8");
assert.ok(documentSrc.includes("process.env.NODE_ENV === 'production'"));
assert.ok(documentSrc.includes("gaBootstrapInline"));
assert.ok(!documentSrc.includes("googletagmanager.com/gtag/js"));

const appSrc = fs.readFileSync(path.join(root, "web/app/pages/_app.js"), "utf8");
assert.ok(appSrc.includes("routeChangeComplete"));
assert.ok(appSrc.includes("pageview"));

const pageSrc = fs.readFileSync(path.join(root, "web/app/pages/no-track.js"), "utf8");
assert.ok(pageSrc.includes('content="noindex, nofollow"'));
assert.ok(pageSrc.includes("getServerSideProps"));
assert.ok(pageSrc.includes("/no-track?off=1"));
assert.ok(pageSrc.includes("serializeOptOutCookie"));

console.log("test_no_ga_cookie.js: all assertions passed");
