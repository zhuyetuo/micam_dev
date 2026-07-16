#!/usr/bin/env bash
# Generate the lowercase MD5 hash that MILOCO_PASSWORD expects.
#
# Usage: ./scripts/gen_password.sh "your-chosen-password"
set -euo pipefail

if [ $# -ne 1 ] || [ -z "$1" ]; then
  echo "Usage: $0 <plain-password>" >&2
  exit 1
fi

if command -v md5sum >/dev/null 2>&1; then
  printf '%s' "$1" | md5sum | awk '{print $1}'
elif command -v md5 >/dev/null 2>&1; then
  printf '%s' "$1" | md5 | awk '{print tolower($0)}'
else
  echo "Neither md5sum nor md5 found on this system." >&2
  exit 1
fi
