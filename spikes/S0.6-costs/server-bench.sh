#!/bin/sh
# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
#
# Spike S0.6 on a Docker host (e.g. the ARM server running S0.1): print the machine's
# resources, then run measure.py in a throwaway container on the most recent demos the S0.1
# bot downloaded. Read-only on the bot's volume; changes nothing on the host.
#
# Usage (as a user allowed to run docker):
#   curl -fsSL https://raw.githubusercontent.com/untraded/untraded/main/spikes/S0.6-costs/server-bench.sh | sh
# Optional: DEMOS=5 (number of demos), BRANCH=main (where to fetch measure.py from).
set -eu

DEMOS="${DEMOS:-5}"
BRANCH="${BRANCH:-main}"
RAW="https://raw.githubusercontent.com/untraded/untraded/${BRANCH}/spikes/S0.6-costs/measure.py"

echo "=== Machine"
uname -srm
grep PRETTY_NAME /etc/os-release || true
nproc
lscpu | grep -E 'Model name|Vendor ID|^CPU\(s\)|Thread|MHz' || true
free -h
df -h / /var/lib/docker 2>/dev/null || df -h /
uptime
echo "=== Docker"
docker --version
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
docker stats --no-stream --format '{{.Name}}\tCPU {{.CPUPerc}}\tRAM {{.MemUsage}}'
echo "daemon.json: $(cat /etc/docker/daemon.json 2>/dev/null || echo absent)"

VOLUME=$(docker volume ls --format '{{.Name}}' | grep 'spike-valve-data$' | head -n 1)
if [ -z "$VOLUME" ]; then
  echo "no spike-valve-data volume: nothing to benchmark"
  exit 0
fi
echo "=== Demos in volume $VOLUME"
docker run --rm -v "$VOLUME:/data:ro" alpine:3.22 sh -c \
  'ls /data/corpus/inbox | wc -l; du -sh /data/corpus/inbox;
   find /data/corpus/inbox -name "*.dem.bz2" -exec stat -c %s {} + | sort -n |
   awk "{a[NR]=\$1} END {print \"median .dem.bz2 bytes:\", a[int((NR+1)/2)]}"'

echo "=== Benchmark on the $DEMOS most recent demos (python:3.14-slim, $(uname -m))"
docker run --rm -v "$VOLUME:/data:ro" -e DEMOS="$DEMOS" -e RAW="$RAW" python:3.14-slim sh -c '
  set -e
  pip install --quiet --root-user-action=ignore demoparser2==0.42.0 polars==2.0.0 pyarrow==26.0.0
  mkdir -p /work/demos
  python -c "import urllib.request, os; urllib.request.urlretrieve(os.environ[\"RAW\"], \"/work/measure.py\")"
  for f in $(ls -t /data/corpus/inbox/*.dem.bz2 | head -n "$DEMOS"); do ln -s "$f" /work/demos/; done
  python /work/measure.py /work/demos
'
