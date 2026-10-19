#!/usr/bin/env bash
# This copies the latest webcam image to stable filenames (raw, large, small).
# Source: the camera's native FTP snapshots under camftp/ (camftp/<MachineName>/YYYY-MM-DD/001/jpg/HH/MM/SS[..].jpg),
# falling back to the flat wxcam* uploads (Agent DVR / PC uploader) if the camera has sent nothing for 2 min.
# Every output is written to a temp file in the same directory and then
# atomically renamed (mv), so readers (web, cam_archive.sh, the sunshine
# classifier) never see a half-written JPEG.
set -eu

CUM="/var/www/rwc/html/cumulus"
CAMFTP="$CUM/camftp"
DST="$CUM/skycam_raw.jpg"
DST_LG="$CUM/skycam_large.jpg"
DST_SM="$CUM/skycam_small.jpg"

ITER=100000000
FREQ=3

# The camera's FTP JPEGs carry video-range luma (black ~16, JFIF-tagged as full range), so they look flat and
# desaturated next to the Agent DVR-decoded stream the sunshine models were trained on. Expand luma 16-235 -> 0-255
# and give chroma a small 1.05 boost (fitted on same-minute old/new frames, Oct 16 17:07 PT). Camera files only.
CAM_FIX="lutyuv=y='clip((val-16)*255/219,0,255)':u='clip((val-128)*1.05+128,0,255)':v='clip((val-128)*1.05+128,0,255)'"

# encode SRC -> DST via DST.tmp + rename. -f mjpeg because the temp name has no .jpg extension.
encode() {
  local src="$1" dst="$2"; shift 2
  ffmpeg -hide_banner -loglevel error -y -i "$src" "$@" -f mjpeg "$dst.tmp" && mv -f "$dst.tmp" "$dst"
}

# Complete JPEG: starts with SOI and has EOI (FFD9) within the last 32 bytes
# (Dahua appends an 8-byte "dhav" trailer after EOI).
complete_jpeg() {
  local f="$1"
  [ -s "$f" ] || return 1
  [ "$(head -c2 "$f" | od -An -tx1 | tr -d ' \n')" = "ffd8" ] || return 1
  tail -c32 "$f" | od -An -tx1 | tr -d ' \n' | grep -q "ffd9"
}

pick() {
  # Newest camera file may be mid-upload (camera writes in place): take the second-newest from the last 2 min.
  local img
  img=$(find "$CAMFTP" -type f -name '*.jpg' -mmin -2 -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n2 | head -n1 | cut -d' ' -f2-)
  if [ -z "$img" ]; then
    img=$(ls -rAt "$CUM"/wxcam* 2>/dev/null | tail -n2 | head -n1)
  fi
  printf '%s' "$img"
}

for ((n=0;n<$ITER;n++))
do
  IMG=$(pick || true)
  if [ -z "$IMG" ] || ! complete_jpeg "$IMG"; then sleep $FREQ; continue; fi
  VF=()
  case "$IMG" in "$CAMFTP"/*) VF=(-vf "$CAM_FIX") ;; esac
  # Re-encode the upload straight into a temp file (never in place).
  encode "$IMG" "$DST" ${VF[@]+"${VF[@]}"} -q:v 3 || { sleep $FREQ; continue; }
  encode "$DST" "$DST_LG" -vf scale="1560:-1" || true
  encode "$DST" "$DST_SM" -vf scale="740:-1" || true
  sleep $FREQ
done
