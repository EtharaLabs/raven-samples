"""Oracle-side collection routine: finalize the authoritative artifacts at teardown.

Runs as ``python -m raven_ar9.collect`` in the ORACLE container (task.toml declares
``[[verifier.collect]] service = "oracle"``). It SIGTERMs the in-container
``raven_ar9.server`` (found via ``/proc``),
whose ``flush()`` writes the authoritative event log, then waits for that file before
emitting an absence sentinel.

GAP 1 — path reconciliation (end-to-end filename agreement, Defect 6)
--------------------------------------------------------------------
The oracle writes BOTH authoritative files to absolute oracle-only paths that the
top-level ``[[artifacts]]`` ``source`` fields in task.toml point at:

    event log : RAVEN_EVENTLOG_OUT   default /authority/eventlog.json
    app-state : RAVEN_APPSTATE_OUT   default /authority/appstate.json

Harbor re-materializes each collected artifact in the SEPARATE verifier at its ORIGINAL
``source`` path (no translation), so both files reappear at /authority/<name>. task.toml
sets ``[verifier.environment.env] RAVEN_VERIFIER_WORKSPACE = /authority``, and tests/test.sh
passes that as ``--workspace``; ``tests/score.py`` then resolves ``<workspace>/eventlog.json``
(load_artifact) and ``<workspace>/appstate.json`` (load_state). The three dirs — the oracle
write dir, the artifact source dir, and RAVEN_VERIFIER_WORKSPACE — are therefore the SAME
``/authority``, and the two filenames match score.py's resolver exactly. The authoritative
source stays the oracle-only /authority file; the verifier never mounts the oracle fs, only
the collected artifacts.

GAP 2 — the app-state dump itself is produced here via ``raven_ar9.statedump``: a
trusted, collect-time, oracle-only routine (NOT an MCP tool). It is fail-closed — a
valid JSON object or nothing — so score.py never reads a partial dump.
"""

from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path
from typing import Any

from raven_ar9 import statedump

DEFAULT_EVENTLOG = "/authority/eventlog.json"
DEFAULT_APPSTATE = "/authority/appstate.json"
EMPTY_LOG = {"event_log": {"past_events": []}}
WAIT_SECONDS = 15


def _server_pids() -> list[int]:
    pids: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return pids
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if "raven_ar9.server" in cmdline:
            pids.append(int(entry.name))
    return pids


def _load_artifact(target: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _server_dump_is_rich(appstate: Path) -> bool:
    """True if a server-written app-state dump with live app sections already exists.

    The server's own flush/snapshot (with live apps) emits Calendar/CabApp/... sections;
    collect.py runs only after SIGTERMing that server, so its own dump is forced to
    apps=None (Files-only). Overwriting a rich dump with a Files-only one would silently
    re-zero the room-derivation predicates, so collect defers whenever a richer dump is
    already on disk.
    """
    try:
        if not (appstate.exists() and appstate.stat().st_size > 0):
            return False
        data = json.loads(appstate.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - unreadable dump is treated as absent
        return False
    return isinstance(data, dict) and any(k != "Files" for k in data)


def _dump_appstate(artifact: dict[str, Any] | None, target: Path) -> bool:
    try:
        return statedump.dump_appstate(target, apps=None, artifact=artifact)
    except Exception:  # noqa: BLE001 - the dump is best-effort; the event log is authoritative
        return False


def main() -> int:
    target = Path(os.environ.get("RAVEN_EVENTLOG_OUT", DEFAULT_EVENTLOG))
    appstate = Path(os.environ.get("RAVEN_APPSTATE_OUT", DEFAULT_APPSTATE))
    target.parent.mkdir(parents=True, exist_ok=True)
    flag = Path(os.environ.get("RAVEN_REPLAY_FLAG", "/authority/replay_fired.json"))
    if flag.exists():
        print(f"raven-ar9: oracle replay provenance -> {flag.read_text(encoding='utf-8').strip()}")
    for pid in _server_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if target.exists() and target.stat().st_size > 0:
            if _server_dump_is_rich(appstate):
                print(f"raven-ar9: event log at {target}; rich app-state dump already written by server at {appstate}")
                return 0
            artifact = _load_artifact(target)
            if _dump_appstate(artifact, appstate):
                print(f"raven-ar9: event log at {target}; app-state dump at {appstate}")
            else:
                print(f"raven-ar9: event log at {target}; no app-state dump written (scorer will project)")
            return 0
        time.sleep(0.5)
    target.write_text(json.dumps(EMPTY_LOG), encoding="utf-8")
    print(f"raven-ar9: event log absent, wrote empty-log sentinel to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
