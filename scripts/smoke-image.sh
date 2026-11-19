#!/usr/bin/env bash
set -euo pipefail

# Smoke test: wait for the container to be healthy, then curl /healthz, /readyz, /
MAX_WAIT=30
WAITED=0

until curl -fsS "http://localhost:8000/healthz" >/dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "ERROR: container did not start within ${MAX_WAIT}s"
    docker logs weather-test
    exit 1
  fi
  sleep 1
  WAITED=$((WAITED + 1))
done

echo "Container started after ${WAITED}s"

# Curl the three endpoints; fail on any error
for path in /healthz /readyz /; do
  echo "Checking ${path} ..."
  if ! RESP=$(curl -fsS "http://localhost:8000${path}"); then
    echo "FAIL: curl ${path} returned non-zero"
    docker logs weather-test
    exit 1
  fi
  echo "  OK: ${RESP}"
done

echo "All smoke checks passed"
