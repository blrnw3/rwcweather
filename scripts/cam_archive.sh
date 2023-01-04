#!/usr/bin/env bash
# This copies wxcam images to long-term storage, and deletes old storage
set -eu

DST_XL="/var/www/rwc/html/cumulus/skycam_raw.jpg"
DST_LG="/var/www/rwc/html/cumulus/skycam_large.jpg"
DST_SM="/var/www/rwc/html/cumulus/skycam_small.jpg"
DST_ARCHIVE="/var/www/rwc/html/cumulus/camdump"

TS=$(date +"%Y%m%d_%H%M")

cp "$DST_SM" "${DST_ARCHIVE}/sky_sm/${TS}.jpg"
cp "$DST_LG" "${DST_ARCHIVE}/sky_lg/${TS}.jpg"
cp "$DST_XL" "${DST_ARCHIVE}/sky_xl/${TS}.jpg"

find "${DST_ARCHIVE}/sky_xl/" -mtime +1 -regex ".*[12346789]\.jpg" -delete
find "${DST_ARCHIVE}/sky_lg/" -mtime +3 -regex ".*[1234567895]\.jpg" -delete
find "${DST_ARCHIVE}/sky_sm/" -mtime +7 -delete
find "${DST_ARCHIVE}/sky_xl/" -mtime +7 -regex ".*[1245][0]\.jpg" -delete
find "${DST_ARCHIVE}/sky_xl/" -mtime +7 -regex ".*[235][5]\.jpg" -delete
find "${DST_ARCHIVE}/sky_xl/" -mtime +30 -regex ".*[14][5]\.jpg" -delete
