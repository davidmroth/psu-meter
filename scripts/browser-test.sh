#!/usr/bin/env bash
# Runs the energy widget browser tests against this meter's real page, in Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENERGY_COST_DIR="${ENERGY_COST_DIR:-${ROOT}/../energy-cost}"
exec "${ENERGY_COST_DIR}/browser-testing/run-in-docker.sh" "${ROOT}" "$@"
