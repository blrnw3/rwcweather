#!/usr/bin/env bash
# This copies the latest wxcam image to stable filenames (raw, large, small).
# Every output is written to a temp file in the same directory and then
# atomically renamed (mv), so readers (web, cam_archive.sh, the sunshine
# classifier) never see a half-written JPEG.
set -eu

DST="/var/www/rwc/html/cumulus/skycam_raw.jpg"
DST_LG="/var/www/rwc/html/cumulus/skycam_large.jpg"
DST_SM="/var/www/rwc/html/cumulus/skycam_small.jpg"

ITER=100000000
FREQ=3

# encode SRC -> DST via DST.tmp + rename. -f mjpeg because the temp name has no .jpg extension.
encode() {
  local src="$1" dst="$2"; shift 2
  ffmpeg -hide_banner -loglevel error -y -i "$src" "$@" -f mjpeg "$dst.tmp" && mv -f "$dst.tmp" "$dst"
}

for ((n=0;n<$ITER;n++))
do
  # Most recent file could be mid-upload
  IMG=$(ls -rAt /var/www/rwc/html/cumulus/wxcam* | tail -n2 | head -n1)
  # Re-encode the upload straight into a temp file (never in place).
  encode "$IMG" "$DST" -q:v 20 || { sleep $FREQ; continue; }
  encode "$DST" "$DST_LG" -vf scale="1560:-1" || true
  encode "$DST" "$DST_SM" -vf scale="740:-1" || true
  sleep $FREQ
done
