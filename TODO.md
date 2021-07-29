# Active issues
## High pri
* Dependent radio groups
* Wind direction chart
* More efficient fetch for long-range 'latest' obs data (7d is slow on LTE)
* Matrix: change year
* Try SSR again
* URL modification based on selectors

# v1 (priority list, deploy as each point developed)
TARGET DATE: 01 Jan 2022
## Major
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