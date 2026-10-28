#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENERGY_COST="$(cd "${ROOT}/../energy-cost" && pwd)"

docker run --rm \
  -v "${ROOT}:/src:ro" \
  -v "${ENERGY_COST}:/energy-cost-src:ro" \
  python:3.12-slim \
  bash -c "cp -r /energy-cost-src /energy-cost && cp -r /src /work && cd /work \
    && pip install -q --root-user-action=ignore /energy-cost '.[test]' \
    && pytest -p no:cacheprovider"
