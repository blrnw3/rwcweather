#!/usr/bin/env bash
# This copies wxcam images to long-term storage, and deletes old storage.
# Copies go to a hidden .part file in the target dir, then are atomically renamed.
set -eu

DST_XL="/var/www/rwc/html/cumulus/skycam_raw.jpg"
DST_LG="/var/www/rwc/html/cumulus/skycam_large.jpg"
DST_SM="/var/www/rwc/html/cumulus/skycam_small.jpg"
DST_ARCHIVE="/var/www/rwc/html/cumulus/camdump"

TS=$(date +"%Y%m%d_%H%M")

archive() {
  local src="$1" dir="$2"
  local tmp="${dir}/.${TS}.jpg.part"
  cp "$src" "$tmp" && mv -f "$tmp" "${dir}/${TS}.jpg"
}

archive "$DST_SM" "${DST_ARCHIVE}/sky_sm"
archive "$DST_LG" "${DST_ARCHIVE}/sky_lg"
archive "$DST_XL" "${DST_ARCHIVE}/sky_xl"

# clean up any stale temp files left by an interrupted run
find "${DST_ARCHIVE}/" -name ".*.jpg.part" -mmin +10 -delete

find "${DST_ARCHIVE}/sky_xl/" -mmin +300 -regex ".*[123456789]\.jpg" -delete
find "${DST_ARCHIVE}/sky_lg/" -mtime +2 -regex ".*[123456789]\.jpg" -delete
find "${DST_ARCHIVE}/sky_sm/" -mtime +1 -delete
find "${DST_ARCHIVE}/sky_xl/" -mtime +2 -regex ".*[1245][0]\.jpg" -delete
find "${DST_ARCHIVE}/sky_xl/" -mtime +7 -regex ".*30\.jpg" -delete
find "${DST_ARCHIVE}/sky_xl/" -mtime +7 -regex ".*[13579]00.jpg" -delete
find "${DST_ARCHIVE}/sky_lg/" -mtime +7 -regex ".*[1245][0]\.jpg" -delete

# camera native FTP spool (camftp/<MachineName>/YYYY-MM-DD/001/jpg/HH/MM/SS*.jpg): keep 30 min
find /var/www/rwc/html/cumulus/camftp/ -type f -name "*.jpg" -mmin +30 -delete
find /var/www/rwc/html/cumulus/camftp/ -mindepth 2 -type d -empty -delete
