#!/usr/bin/env bash
# This copies wxcam images to long-term storage
set -eu

DST_XL="/var/www/rwc/html/cumulus/skycam_raw.jpg"
DST_LG="/var/www/rwc/html/cumulus/skycam_large.jpg"
DST_SM="/var/www/rwc/html/cumulus/skycam_small.jpg"
DST_ARCHIVE="/var/www/rwc/html/cumulus/camdump"

TS=$(date +"%Y%d%m_%H%M")

cp "$DST_SM" "${DST_ARCHIVE}/sky_sm/${TS}.jpg"
cp "$DST_LG" "${DST_ARCHIVE}/sky_lg/${TS}.jpg"
cp "$DST_XL" "${DST_ARCHIVE}/sky_xl/${TS}.jpg"

find "${DST_ARCHIVE}/sky_xl/" -mtime +2 -regex ".*[12346789]\.jpg" -delete
find "${DST_ARCHIVE}/sky_lg/" -mtime +7 -regex ".*[12346789]\.jpg" -delete
find "${DST_ARCHIVE}/sky_sm/" -mtime +30 -regex ".*[12346789]\.jpg" -delete
