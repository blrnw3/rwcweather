# Active issues
## High pri
* Times of extremes and moon on dash are localized - should be PT
* Rain in db should not be cumulative per day but give actual vals
* URL modification based on selectors
* backfill data for 2020

# v1 (priority list, deploy as each point developed)
TARGET DATE: 01 Jun 2022
## Major
* Try SSR again
* Dependent radio groups
* Webcam: new page and display on dashboard
* Forecast: new page and display on dash
* Climate: new page and integrate into dash and all existing pages
* Charts: date selector
## Minor
* Feels-like
* Smart update frequencies and caching
* AQI smoothing
* UX: explore use of a real picture for logo

# v2 (priority list)
TARGET DATE: TBD
* More rain details - dry/wet spells etc.
* Data source substitution - when local data unavailable switch for nearby source
* Annual reports
* Monthly reports
* Webcam timelapses
* Sunshine tracking
* System page with indoor conditions etc.
* Admin page for data correction etc.
* Change xtremes (e.g. max hourly temp increase)
* Events (manual stuff like fog, snow, thunder, other comments)

# v? (unordered wish list)
* nw3weather feature parity
* Photo albums
* live webcam

server {
    server_name .redwoodcityweather.com;
    return 301 https://rwcweather.com$request_uri;
}