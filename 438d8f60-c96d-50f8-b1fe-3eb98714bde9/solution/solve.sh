#!/bin/sh
# Author-maintained for this ARE bundle; tests/score.py is the reward authority. No generator ships.
# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 334129c509f28f649dc134eaa7540cf63ffdd5c1529412a6353fd3f9157812ab
# FORGE-CANARY-END
#
# Reference-oracle trigger. This script runs ONLY in the oracle-agent leg (Harbor uploads
# solution/ and runs solve.sh for agent=oracle alone; nop and model agents never receive it).
# It sends the pre-shared secret to the oracle sidecar's single-shot replay listener over the
# internal oracle_net. On a valid secret the sidecar runs the in-process reference oracle and
# writes the authoritative full-reward event log. The secret's plaintext lives ONLY here in
# solution/, which ships in no image; the sidecar holds only its SHA-256.
set -eu

SECRET="3b4515bdc40fc263100206550b7ca4293649a8be36a9a1d7c6be1447a132bfb5"
TRIGGER_DIR="${RAVEN_TRIGGER_DIR:-/trigger}"
REQ="$TRIGGER_DIR/replay.request"
DONE="$TRIGGER_DIR/replay.done"

python3 - "$SECRET" "$REQ" "$DONE" <<'PYEOF'
import os, sys, time
secret, req_path, done_path = sys.argv[1], sys.argv[2], sys.argv[3]
tmp = req_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    fh.write(secret + "\n")
    fh.flush()
    os.fsync(fh.fileno())
os.replace(tmp, req_path)
deadline = time.time() + 1500
while time.time() < deadline:
    try:
        with open(done_path, "r", encoding="utf-8") as fh:
            verdict = fh.read().strip()
    except OSError:
        time.sleep(1.0)
        continue
    if verdict.startswith("ok"):
        print("oracle replay confirmed via trigger volume", flush=True)
        sys.exit(0)
    print("oracle replay refused: " + verdict, file=sys.stderr, flush=True)
    sys.exit(1)
print("timed out waiting for oracle replay", file=sys.stderr, flush=True)
sys.exit(1)
PYEOF
