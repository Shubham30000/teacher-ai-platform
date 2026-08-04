#!/usr/bin/env bash
# Runs the full Phase 1A test suite with a short summary at the end.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -v --tb=short "$@"
