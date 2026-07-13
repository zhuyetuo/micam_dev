#!/usr/bin/env bash
# Record a go2rtc RTSP stream into rotating MP4 segments, using stream copy
# (no re-encode) so it costs no CPU beyond the network read.
#
# Usage: ./scripts/record_segments.sh <stream_name> [output_dir] [segment_seconds]
# Example: ./scripts/record_segments.sh cam0 ./recordings/cam0 600
set -euo pipefail

STREAM_NAME="${1:?usage: record_segments.sh <stream_name> [output_dir] [segment_seconds]}"
OUT_DIR="${2:-./recordings/${STREAM_NAME}}"
SEGMENT_SECONDS="${3:-600}"
RTSP_HOST="${RTSP_HOST:-127.0.0.1}"
RTSP_PORT="${RTSP_PORT:-8554}"

mkdir -p "$OUT_DIR"

exec ffmpeg -rtsp_transport tcp \
  -i "rtsp://${RTSP_HOST}:${RTSP_PORT}/${STREAM_NAME}" \
  -c copy \
  -f segment -segment_time "${SEGMENT_SECONDS}" -segment_format mp4 \
  -reset_timestamps 1 -strftime 1 \
  "${OUT_DIR}/%Y%m%d_%H%M%S.mp4"
