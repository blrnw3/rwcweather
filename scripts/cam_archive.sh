#!/usr/bin/env bash
# This copies wxcam images to long-term storage, and deletes old storage.
# Copies go to a hidden .part file in the target dir, then are atomically renamed.
set -eu

CUM="${RWC_CUM:-/var/www/rwc/html/cumulus}"
DST_XL="$CUM/skycam_raw.jpg"
DST_LG="$CUM/skycam_large.jpg"
DST_SM="$CUM/skycam_small.jpg"
DST_ARCHIVE="$CUM/camdump"
# Last archived md5 per size, to skip repeats.
STATE_DIR="${CAM_ARCHIVE_STATE:-$HOME/.cache/cam_archive}"
# cam_save.sh rewrites the outputs every few seconds while it has a live source; older means no live source.
MAX_AGE_MIN=3

TS="${CAM_ARCHIVE_TS:-$(date +"%Y%m%d_%H%M")}"
mkdir -p "$STATE_DIR"

# Skips (never archives) an image that is missing, empty, older than MAX_AGE_MIN, or byte-identical to the last
# one archived: a frozen camera otherwise filled the archive with days of one image (2026-07-17..22).
archive() {
  local src="$1" dir="$2" name="$3"
  local tmp="${dir}/.${TS}.jpg.part" last="${STATE_DIR}/${name}.md5" sum
  [ -n "$(find "$src" -mmin -"$MAX_AGE_MIN" 2>/dev/null)" ] || return 0
  cp "$src" "$tmp" || return 0
  sum=$(md5sum < "$tmp" | cut -d' ' -f1)
  if [ ! -s "$tmp" ] || { [ -f "$last" ] && [ "$(cat "$last")" = "$sum" ]; }; then
    rm -f "$tmp"; return 0
  fi
  mv -f "$tmp" "${dir}/${TS}.jpg" && printf '%s\n' "$sum" > "$last"
}

archive "$DST_SM" "${DST_ARCHIVE}/sky_sm" sm
archive "$DST_LG" "${DST_ARCHIVE}/sky_lg" lg
archive "$DST_XL" "${DST_ARCHIVE}/sky_xl" xl

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
find "$CUM/camftp/" -type f -name "*.jpg" -mmin +30 -delete
find "$CUM/camftp/" -mindepth 2 -type d -empty -delete
