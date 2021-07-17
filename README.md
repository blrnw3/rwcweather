# Redwood City Weather

Code that powers [rwcwx](http://redwoodcityweather.com)

## Structure
Python3 Flask app with mysql db

## Data
Davis VP2 weather station sending readings to a server running Cumulus MX using WeatherLink Live

## Development
* To simulate the prod cron scripts, run dev/run_cron.sh
* To start the webserver: FLASK_APP=rwcwx/main.py flask run

## Settings (as env vars)
* MYSQL_URL - not needed in local but needed elsewhere

## Deployment
See /deploy

## infra TODOs
* Switch to FastAPI
* Dockerize: https://fastapi.tiangolo.com/deployment/docker/
