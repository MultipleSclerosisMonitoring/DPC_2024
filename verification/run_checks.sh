#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

python -m py_compile \
  api.py \
  msCodeID/codeid_processor.py \
  msGait/movement_detector.py \
  msTools/data_manager.py \
  msTools/settings.py \
  msTools/timeutils.py \
  msTools/i18n.py \
  ms_monitoring/find_gait.py \
  ms_monitoring/find_mscodeids.py \
  tests/test_data_manager.py \
  tests/test_movement_detector.py \
  tests/test_settings.py

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests -q

PYRIGHT_PYTHON="${PYRIGHT_PYTHON:-/home/jordieres/soft/sclerosis/vpy-ms/bin/python}"

if [ -x "$PYRIGHT_PYTHON" ]; then
  "$PYRIGHT_PYTHON" -m pyright
else
  echo "Configured PYRIGHT_PYTHON not found; skipping static type checks."
fi
