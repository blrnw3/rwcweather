#!/usr/bin/env bash
# This copies the latest wxcam image to a stable filename
set -eu

DST="/var/www/rwc/html/cumulus/skycam_raw.jpg"
DST_LG="/var/www/rwc/html/cumulus/skycam_large.jpg"
DST_SM="/var/www/rwc/html/cumulus/skycam_small.jpg"
DST_ARCHIVE="/var/www/rwc/html/cumulus/camdump"

ITER=100000000
FREQ=3

for ((n=0;n<$ITER;n++))
do
  TS=$(date +"%H%M%S")
  # Most recent file could be mid-upload
  IMG=$(ls -rAt /var/www/rwc/html/cumulus/wxcam* | tail -n2 | head -n1)
  cp "$IMG" "$DST.tmp" && mv "$DST.tmp" "$DST"
  ffmpeg -hide_banner -loglevel error -y -i "$DST" -q:v 20 "$DST"
  ffmpeg -hide_banner -loglevel error -y -i "$DST" -vf scale="1560:-1" "$DST_LG"
  ffmpeg -hide_banner -loglevel error -y -i "$DST" -vf scale="740:-1" "$DST_SM"
  sleep $FREQ
done
