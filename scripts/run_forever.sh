#!/usr/bin/env bash
# Scheduler loop. Default is rehearsal (no Reddit writes).
#
# Unattended live sends are not started from this script in the Hashmark setup.
# A parent-managed saved routine must set LIVE=1 *and* pass activation gates
# (Hashmark currently fails those gates on purpose).
#
#   bash scripts/run_forever.sh            # dry-run ticks
#   DRY=1 bash scripts/run_forever.sh      # same (explicit rehearsal)
#   LIVE=1 bash scripts/run_forever.sh     # live — refused when RAP_PROFILE=hashmark
#   INTERVAL=600 bash scripts/run_forever.sh
set -euo pipefail
INTERVAL="${INTERVAL:-300}"
LIVE_FLAG=""
if [[ "${LIVE:-0}" == "1" && "${DRY:-0}" != "1" ]]; then
  LIVE_FLAG="--live"
fi
if [[ "${RAP_PROFILE:-}" == "hashmark" && -n "${LIVE_FLAG}" ]]; then
  echo "Hashmark live loop is disabled. Leave LIVE unset; posting stays draft-only until a parent-managed saved routine authorizes a supported backend." >&2
  exit 1
fi
PROFILE_FLAG=()
if [[ -n "${RAP_PROFILE:-}" ]]; then
  PROFILE_FLAG=(--profile "${RAP_PROFILE}")
fi
echo "reddit-autopilot loop starting (interval=${INTERVAL}s, live=${LIVE_FLAG:-no}, profile=${RAP_PROFILE:-default})"
while true; do
  date "+%Y-%m-%d %H:%M:%S  tick"
  rap "${PROFILE_FLAG[@]}" run ${LIVE_FLAG} || echo "tick failed (will retry)"
  sleep "${INTERVAL}"
done
