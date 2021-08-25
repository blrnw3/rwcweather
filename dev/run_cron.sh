#!/usr/bin/env bash

# Run all the scripts needed to fetch and save data

set -eu

function onkill()
{
  echo "Killing ${ID}"
  kill $ID
}

trap onkill EXIT

python rwcwx/job/get_external.py -o out
curl https://rwcweather.com/cumulus/realtime.txt > out/realtime.txt
python rwcwx/job/save_latest.py -o /Users/bmasscheleinrodgers/rwcweather/out/realtime.txt -e /Users/bmasscheleinrodgers/rwcweather/out &
ID=$!
sleep 10

while true
do
  python rwcwx/job/get_external.py -o out
  curl https://rwcweather.com/cumulus/realtime.txt > out/realtime.txt
  sleep 30
  curl https://rwcweather.com/cumulus/realtime.txt > out/realtime.txt
  sleep 30
  curl https://rwcweather.com/cumulus/realtime.txt > out/realtime.txt
  sleep 30
done
