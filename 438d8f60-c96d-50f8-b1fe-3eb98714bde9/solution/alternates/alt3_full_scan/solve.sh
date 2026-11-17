#!/bin/sh
# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 73ee2510548eccff2d3de1fc4f8a887ed64593b846d8098694d137dde7e47419
# FORGE-CANARY-END
set -eu
OUT="${1:-logs/artifacts}"
MODE=alt3_chats
SEED="${2:-}"
python3 - "$OUT" "$MODE" $SEED <<'PYEOF'
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path.cwd()))
from solution.scenario import _write, expected_full_success, run_mode, self_check

target = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else None
payload = run_mode(mode, seed)
written = _write(target, payload)
result = self_check(written, mode)
print("mode=%s seed=%s reward=%s full_success=%s wrote %s" % (
    mode, payload["seed"], result.get("reward"), result.get("full_success"), written))
if "skipped" not in result and bool(result.get("full_success")) != expected_full_success(mode):
    print("UNEXPECTED: mode %s full_success=%s" % (mode, result.get("full_success")))
    sys.exit(1)
PYEOF
