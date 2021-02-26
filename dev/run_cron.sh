#!/usr/bin/env bash

# Run all the scripts needed to fetch and save data

set -eu

curl https://redwoodcityweather.com/cumulus/realtime.txt > out/realtime.txt
python rwcwx/job/save_latest.py -o /Users/bmasscheleinrodgers/rwcweather/out/realtime.txt -e /Users/bmasscheleinrodgers/rwcweather/out &
sleep 10

while true
do
  python rwcwx/job/get_external.py -o out
  curl https://redwoodcityweather.com/cumulus/realtime.txt > out/realtime.txt
  sleep 30
  curl https://redwoodcityweather.com/cumulus/realtime.txt > out/realtime.txt
  sleep 30
  curl https://redwoodcityweather.com/cumulus/realtime.txt > out/realtime.txt
  sleep 30
done
