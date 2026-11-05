#!/usr/bin/env bash
# Run the reddit-autopilot scheduler in a loop (every 5 minutes by default).
# Each tick processes whatever is due, using the live browser session.
#
#   bash scripts/run_forever.sh            # live
#   DRY=1 bash scripts/run_forever.sh      # rehearsal only
#   INTERVAL=600 bash scripts/run_forever.sh
set -euo pipefail
INTERVAL="${INTERVAL:-300}"
LIVE_FLAG="--live"
if [[ "${DRY:-0}" == "1" ]]; then LIVE_FLAG=""; fi
echo "reddit-autopilot loop starting (interval=${INTERVAL}s, live=${LIVE_FLAG:-no})"
while true; do
  date "+%Y-%m-%d %H:%M:%S  tick"
  rap run ${LIVE_FLAG} || echo "tick failed (will retry)"
  sleep "${INTERVAL}"
done
