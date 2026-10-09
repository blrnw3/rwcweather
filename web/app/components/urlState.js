import { useRouter } from "next/router";
import { useCallback, useEffect, useRef, useState } from "react";

// Page selections mirrored in the URL query string, so a link restores the view.
//
// `spec` maps each state key to:
//   param    query-string name (defaults to the key)
//   def(s)   default value, given the state parsed so far (keys are resolved in
//            spec order, so later defaults can depend on earlier keys)
//   valid(v, s)  whether a value is allowed, given the state parsed so far
//   toUrl / fromUrl  optional readable encoding (e.g. month 3 <-> "mar")
//   use(s)   optional: whether the key matters in this state; unused keys and
//            keys equal to their default are left out of the URL
//
// Static pages render with the defaults (no query on the server), then the query
// is applied once the router is ready, so there is no hydration mismatch. Later
// changes call router.replace with shallow routing: no reload or refetch of the
// page, and no new history entry per click.
export function resolveUrlState(spec, query, base = {}) {
    const state = { ...base };
    for (const [key, field] of Object.entries(spec)) {
        const param = field.param || key;
        let value = query?.[param];
        if (Array.isArray(value)) {
            value = value[0];
        }
        if (value != null && field.fromUrl) {
            value = field.fromUrl(value);
        }
        if (value == null && key in base) {
            value = base[key];
        }
        const valid = value != null && (!field.valid || field.valid(value, state));
        state[key] = valid ? value : field.def(state);
    }
    return state;
}

export function urlQueryFor(spec, state) {
    const query = {};
    for (const [key, field] of Object.entries(spec)) {
        const value = state[key];
        if (value == null || value === "" || value === field.def(state) || (field.use && !field.use(state))) {
            continue;
        }
        query[field.param || key] = field.toUrl ? field.toUrl(value) : String(value);
    }
    return query;
}

function ownQuery(spec, query) {
    const own = {};
    for (const [key, field] of Object.entries(spec)) {
        const param = field.param || key;
        if (query[param] != null) {
            own[param] = Array.isArray(query[param]) ? query[param][0] : query[param];
        }
    }
    return own;
}

function searchString(query) {
    return new URLSearchParams(Object.entries(query).sort()).toString();
}

export function useUrlState(spec) {
    const router = useRouter();
    const specRef = useRef(spec);
    specRef.current = spec;
    const [state, setState] = useState(() => resolveUrlState(spec, {}));
    const [ready, setReady] = useState(false);
    const pending = useRef(null);

    // Read the query after hydration, and again whenever the URL changes from
    // outside (e.g. a nav link to the same page), but not for our own replaces.
    useEffect(() => {
        if (!router.isReady) {
            return;
        }
        const search = searchString(ownQuery(specRef.current, router.query));
        if (pending.current != null) {
            if (pending.current === search) {
                pending.current = null;
            }
            return;
        }
        setState((current) => {
            if (ready && search === searchString(urlQueryFor(specRef.current, current))) {
                return current;
            }
            return resolveUrlState(specRef.current, router.query);
        });
        setReady(true);
    }, [router.isReady, router.asPath]); // eslint-disable-line react-hooks/exhaustive-deps

    // Keep the URL in step with the selections. Only this page's params are
    // touched; defaults and unused params are left out.
    useEffect(() => {
        if (!ready) {
            return;
        }
        const own = urlQueryFor(specRef.current, state);
        if (searchString(own) === searchString(ownQuery(specRef.current, router.query))) {
            return;
        }
        const ownParams = new Set(Object.entries(specRef.current).map(([key, field]) => field.param || key));
        const query = {};
        for (const [param, value] of Object.entries(router.query)) {
            if (!ownParams.has(param)) {
                query[param] = value;
            }
        }
        Object.assign(query, own);
        pending.current = searchString(own);
        router.replace({ pathname: router.pathname, query }, undefined, { shallow: true, scroll: false });
    }, [state, ready]); // eslint-disable-line react-hooks/exhaustive-deps

    // Merge a partial update (object, or function of the current state), then
    // re-resolve so dependent keys fall back to valid defaults.
    const update = useCallback((patch) => {
        setState((current) => {
            const changes = typeof patch === "function" ? patch(current) : patch;
            return resolveUrlState(specRef.current, {}, { ...current, ...changes });
        });
    }, []);

    return [state, update, ready];
}

export function inList(list) {
    return (value) => list.includes(value);
}
