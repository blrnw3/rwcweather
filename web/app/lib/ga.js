// Google Analytics (gtag) helpers. The measurement script is loaded only in
// production, and only when the first-party opt-out cookie is absent.

export const GA_MEASUREMENT_ID = "G-57NHWG35P0";
export const NO_GA_COOKIE = "rwc_no_ga";
export const NO_GA_COOKIE_VALUE = "1";
// About 10 years. Not HttpOnly: the bootstrap script in _document must read it
// on statically generated pages, where the server cannot see the request cookie.
export const NO_GA_MAX_AGE = 10 * 365 * 24 * 60 * 60;

export function isNoTrackPath(pathname) {
    if (!pathname || typeof pathname !== "string") return false;
    const path = pathname.split("?")[0].replace(/\/+$/, "") || "/";
    return path === "/no-track";
}

export function cookieHasOptOut(cookieHeader) {
    if (!cookieHeader || typeof cookieHeader !== "string") return false;
    const parts = cookieHeader.split(";");
    for (let i = 0; i < parts.length; i++) {
        const trimmed = parts[i].trim();
        const eq = trimmed.indexOf("=");
        if (eq < 0) continue;
        const name = trimmed.slice(0, eq).trim();
        let value = trimmed.slice(eq + 1).trim();
        if (value.charCodeAt(0) === 34 && value.charCodeAt(value.length - 1) === 34) {
            value = value.slice(1, -1);
        }
        if (name === NO_GA_COOKIE && value === NO_GA_COOKIE_VALUE) return true;
    }
    return false;
}

export function isHttpsRequest(req) {
    if (!req) return false;
    const headers = req.headers || {};
    const xf = headers["x-forwarded-proto"] || headers["X-Forwarded-Proto"];
    if (typeof xf === "string" && xf.split(",")[0].trim().toLowerCase() === "https") {
        return true;
    }
    if (req.secure === true) return true;
    if (req.connection && req.connection.encrypted) return true;
    return false;
}

export function serializeOptOutCookie({ clear = false, secure = false } = {}) {
    const parts = [
        clear ? (NO_GA_COOKIE + "=") : (NO_GA_COOKIE + "=" + NO_GA_COOKIE_VALUE),
        clear ? "Max-Age=0" : ("Max-Age=" + NO_GA_MAX_AGE),
        "Path=/",
        "SameSite=Lax",
    ];
    if (clear) {
        parts.splice(2, 0, "Expires=Thu, 01 Jan 1970 00:00:00 GMT");
    }
    if (secure) {
        parts.push("Secure");
    }
    return parts.join("; ");
}

export function shouldSendGa({ nodeEnv, cookieHeader, pathname } = {}) {
    if (nodeEnv !== "production") return false;
    if (cookieHasOptOut(cookieHeader)) return false;
    if (isNoTrackPath(pathname)) return false;
    return true;
}

// Inline <head> script for production HTML. ES5 so it runs without transpile.
// If the opt-out cookie is present, gtag.js is never requested. /no-track is
// also skipped so the confirmation page itself does not send a hit.
export function gaBootstrapInline() {
    return (
        "(function(){" +
        "var id=" + JSON.stringify(GA_MEASUREMENT_ID) + ";" +
        "var name=" + JSON.stringify(NO_GA_COOKIE + "=") + ";" +
        "var path=(window.location&&window.location.pathname)||\"\";" +
        "if(path.split(\"?\")[0].replace(/\\/+$/,\"\")===\"/no-track\"){" +
        "window[\"ga-disable-\"+id]=true;return;}" +
        "var cookies=document.cookie?document.cookie.split(\";\"):[];" +
        "for(var i=0;i<cookies.length;i++){" +
        "var c=cookies[i].replace(/^\\s+/,\"\");" +
        "if(c.indexOf(name)===0&&c.substring(name.length)===" + JSON.stringify(NO_GA_COOKIE_VALUE) + "){" +
        "window[\"ga-disable-\"+id]=true;return;}" +
        "}" +
        "window.dataLayer=window.dataLayer||[];" +
        "function gtag(){window.dataLayer.push(arguments);}" +
        "window.gtag=gtag;" +
        "gtag(\"js\",new Date());" +
        "gtag(\"config\",id,{page_path:path});" +
        "var s=document.createElement(\"script\");" +
        "s.async=true;" +
        "s.src=\"https://www.googletagmanager.com/gtag/js?id=\"+id;" +
        "document.head.appendChild(s);" +
        "})();"
    );
}

export function hasOptOutCookie() {
    if (typeof document === "undefined") return false;
    return cookieHasOptOut(document.cookie);
}

export function disableGa() {
    if (typeof window === "undefined") return;
    window["ga-disable-" + GA_MEASUREMENT_ID] = true;
}

export function pageview(url) {
    if (typeof window === "undefined") return;
    if (!shouldSendGa({
        nodeEnv: process.env.NODE_ENV,
        cookieHeader: typeof document === "undefined" ? "" : document.cookie,
        pathname: url || (window.location && window.location.pathname),
    })) {
        disableGa();
        return;
    }
    if (typeof window.gtag !== "function") return;
    window.gtag("config", GA_MEASUREMENT_ID, { page_path: url });
}
