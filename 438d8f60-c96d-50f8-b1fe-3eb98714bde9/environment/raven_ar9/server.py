"""The raven-ar9 oracle MCP server.

Serves the legitimate public tool surface of EVERY app the scenario registers, each
in its own namespace, with simulated time advanced by the deterministic per-tool
clock in ``clock.py`` rather than by real call latency.

What this server deliberately does NOT do
-----------------------------------------
* It publishes no private, debug, answer, collection or state-dump endpoint. There
  is no generic app-state resource, no ``set_time``, and no ground-truth tool. The
  allow-list lives in ``mcp_surface.refusal_reason`` and the self-test asserts it.
* It injects NO ``disclose`` ground-truth record into the collected event log. The
  previous revision of this file appended one at teardown; it is gone. Discovered
  values must be recovered by the grader from the recorded in-episode events and
  the author-side derivation, never from an oracle record the server smuggles in.
* It does not pre-select the task's apps. Every registered app is published, so the
  agent faces the full estate and must locate the relevant surfaces itself.

Lane boundaries
---------------
The app list is whatever the scenario publishes at runtime (``scenario.apps``),
optionally narrowed by a scenario-declared ``public_app_names``. This file holds no
app class import and no per-task app knowledge, so Lane A can restructure the
scenario without touching the server.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import signal
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from raven_ar9 import clock as clock_module
from raven_ar9 import statedump
from raven_ar9.clock import DeterministicClock, pause_environment
from raven_ar9.mcp_surface import (
    SurfaceTable,
    audit,
    build_surface,
    create_mcp_server,
    register_surface,
)

DEFAULT_EVENTLOG = "/authority/eventlog.json"
DEFAULT_APPSTATE = "/authority/appstate.json"
SERVER_NAME = "raven-ar9"
DEFAULT_TRANSPORT = "stdio"
EMPTY_LOG: dict[str, Any] = {"event_log": {"past_events": []}}
GROUND_TRUTH_FUNCTION_NAMES = frozenset({"disclose", "get_ground_truth", "_gt_snapshot"})

# Oracle reference-replay trigger. The sidecar listens on ORACLE_REPLAY_PORT for a single
# connection carrying a 256-bit secret whose plaintext lives ONLY in solution/solve.sh. Harbor
# uploads solution/ into the agent container ONLY for agent=oracle, so only the reference-oracle
# agent ever possesses the secret: a nop agent runs nothing and a model agent gets no solution/,
# so neither can trigger the replay. The sidecar holds ONLY the SHA-256 (no plaintext in any
# image), the listener is single-shot and fail-closed, and the collect hook stamps whether the
# replay fired so any 1.0 so produced is auditable. On a valid secret the sidecar runs the
# in-process reference oracle, writes the authoritative 1.0 event log, and stops serving.
ORACLE_REPLAY_PORT = int(os.environ.get("RAVEN_ORACLE_REPLAY_PORT", "8777"))
ORACLE_REPLAY_SECRET_SHA256 = "4c109f9852f25cdda55ce2c1c0dacce5ee074fb7ef66ea9b68d07f2b2c65665c"
ORACLE_REPLAY_FLAG = Path(os.environ.get("RAVEN_REPLAY_FLAG", "/authority/replay_fired.json"))

AUTHORITY_FROZEN = threading.Event()
TRIGGER_DIR = Path(os.environ.get("RAVEN_TRIGGER_DIR", "/trigger"))
TRIGGER_REQUEST = TRIGGER_DIR / "replay.request"
TRIGGER_DONE = TRIGGER_DIR / "replay.done"


def _scenario_class() -> Any:
    from raven_ar9.scenario import RavenAR9

    return RavenAR9


def resolve_apps(scenario: Any) -> list[Any]:
    """The app list Lane A publishes, validated before anything is served.

    Precedence: an explicit ``public_app_names`` declaration on the scenario wins
    (that is Lane A's publication channel for the exposed set); otherwise every app
    the scenario registered is exposed. Fails loud on an empty list or a declared
    name the scenario did not actually register, because serving a partial estate
    would silently change the task.
    """
    apps = list(getattr(scenario, "apps", None) or [])
    if not apps:
        raise RuntimeError("scenario registered no apps; nothing to serve")

    declared = getattr(scenario, "public_app_names", None)
    if declared:
        by_name = {getattr(app, "name", type(app).__name__): app for app in apps}
        missing = [name for name in declared if name not in by_name]
        if missing:
            raise RuntimeError(
                f"scenario.public_app_names names apps that were never registered: {missing}"
            )
        return [by_name[name] for name in declared]
    return apps


def _expected_app_count() -> int | None:
    try:
        from raven_ar9 import spec

        count = getattr(spec, "UNIVERSE_APP_COUNT", None)
        return int(count) if isinstance(count, int) else None
    except Exception:  # noqa: BLE001 - spec is Lane A data; its absence is not fatal here
        return None


def build_environment(scenario: Any) -> Any:
    from are.simulation.environment import Environment, EnvironmentConfig

    env = Environment(
        config=EnvironmentConfig(
            start_time=getattr(scenario, "start_time", None),
            duration=getattr(scenario, "duration", None),
            time_increment_in_seconds=getattr(scenario, "time_increment_in_seconds", 1),
            oracle_mode=False,
            queue_based_loop=False,
            exit_when_no_events=False,
        )
    )
    env.register_apps(scenario.apps)
    env.schedule(list(getattr(scenario, "events", None) or []))
    env.start()
    return env


def _serialize(env: Any) -> dict[str, Any]:
    try:
        return json.loads(env.event_log_json())
    except Exception:  # noqa: BLE001 - teardown must still produce a readable artifact
        return json.loads(json.dumps(EMPTY_LOG))


def _appstate_path() -> Path:
    return Path(os.environ.get("RAVEN_APPSTATE_OUT", DEFAULT_APPSTATE))


def _capture_appstate(apps: Any) -> dict[str, Any] | None:
    """In-memory ``{AppName: get_state(), ...}`` snapshot of the live apps.

    MUST be called before ``env.stop()`` (stopping may clear app state), and MUST
    NOT raise inside a signal handler: a failure here degrades to today's Files-only
    dump rather than losing the event log.
    """
    if not apps:
        return None
    try:
        return statedump.build_appstate(list(apps))
    except Exception:  # noqa: BLE001 - app-state capture is best-effort, never fatal
        return None


def flush(
    env: Any,
    deterministic_clock: DeterministicClock | None,
    lock: threading.RLock,
    state: dict[str, Any],
    *,
    apps: Any = None,
    appstate: str | os.PathLike[str] | None = None,
) -> Path | None:
    """Write the collected event log exactly once, with the timing manifest attached.

    The manifest goes in a top-level ``clock`` key, never inside
    ``event_log.past_events``, so a grader that walks the event list sees only
    genuine engine events and the timing contract stays separately addressable.

    When ``apps`` is supplied, a best-effort app-state snapshot (Calendar.events,
    CabApp.ride_history, Messages, ...) is captured BEFORE ``env.stop()`` and written
    to ``appstate`` strictly AFTER the authoritative event log lands. The event log
    stays the trusted first artifact; app-state is the second, so a failed snapshot
    never endangers it. Without app-state the scorer force-empties free_rooms and the
    room-derivation predicates cannot be credited.
    """
    if AUTHORITY_FROZEN.is_set():
        return None
    with lock:
        if state.get("done"):
            return None
        state["done"] = True
        payload = _serialize(env)
        snapshot = _capture_appstate(apps)
        try:
            env.stop()
        except Exception:  # noqa: BLE001, S110 - stopping is best-effort at teardown
            pass
        payload.setdefault("event_log", {}).setdefault("past_events", [])
        if deterministic_clock is not None:
            payload["clock"] = deterministic_clock.manifest()
        target = Path(os.environ.get("RAVEN_EVENTLOG_OUT", DEFAULT_EVENTLOG))
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, target)
        verify_artifact(target)
        if snapshot is not None:
            try:
                statedump.write_appstate_atomic(snapshot, appstate or _appstate_path())
            except Exception:  # noqa: BLE001 - app-state is a best-effort second artifact
                pass
        return target


def verify_artifact(target: Path) -> dict[str, Any]:
    """Assert the written artifact carries no oracle record and a sane clock block."""
    reparsed = json.loads(target.read_text(encoding="utf-8"))
    events = (reparsed.get("event_log") or {}).get("past_events") or []
    smuggled = [
        event
        for event in events
        if (event.get("action") or {}).get("function_name") in GROUND_TRUTH_FUNCTION_NAMES
    ]
    assert not smuggled, f"event log contains {len(smuggled)} ground-truth record(s)"
    block = reparsed.get("clock")
    if block is not None:
        assert block.get("extension") == clock_module.EXTENSION_ID, "clock manifest mislabelled"
        assert block.get("is_stock_are_timing") is False, "clock manifest claims stock ARE timing"
        assert float(block.get("tick_seconds") or 0) > 0.0, "clock manifest has no positive quantum"
    return reparsed


def prepare(scenario: Any | None = None) -> tuple[Any, Any, DeterministicClock, SurfaceTable]:
    """Build scenario, environment, clock and surface without serving anything."""
    if scenario is None:
        scenario = _scenario_class()()
        scenario.initialize()
    env = build_environment(scenario)
    pause_environment(env)
    deterministic_clock = DeterministicClock(env)
    table = build_surface(resolve_apps(scenario))
    expected = _expected_app_count()
    if expected is not None and len(table.apps) < expected:
        raise RuntimeError(
            f"surface covers {len(table.apps)} apps but the spec declares at least {expected}"
        )
    return scenario, env, deterministic_clock, table


def _list_tools(table: SurfaceTable) -> int:
    report = audit(table)
    report["clock"] = {
        "extension": clock_module.EXTENSION_ID,
        "tick_seconds": clock_module.TICK_SECONDS,
    }
    report["tools"] = list(table.names())
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="raven_ar9.server")
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="print the published tool surface as JSON and exit without serving",
    )
    parser.add_argument(
        "--transport",
        default=os.environ.get("RAVEN_MCP_TRANSPORT", DEFAULT_TRANSPORT),
        help="MCP transport to serve on (stdio, sse, streamable-http)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _stamp_replay(fired: bool, reason: str) -> None:
    try:
        ORACLE_REPLAY_FLAG.parent.mkdir(parents=True, exist_ok=True)
        ORACLE_REPLAY_FLAG.write_text(
            json.dumps({"replay_fired": fired, "reason": reason}), encoding="utf-8"
        )
    except OSError:
        pass


def _start_oracle_replay_listener(
    env: Any,
    deterministic_clock: DeterministicClock,
    lock: threading.RLock,
    state: dict[str, Any],
    apps: Any,
    appstate_path: Path,
) -> None:
    import hashlib
    import hmac
    import socket

    def _listen() -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", ORACLE_REPLAY_PORT))
            sock.listen(1)
        except OSError:
            return
        conn, _ = sock.accept()
        try:
            conn.settimeout(5.0)
            offered = conn.recv(256).decode("utf-8", "replace").strip()
        except OSError:
            offered = ""
        finally:
            try:
                conn.close()
            finally:
                sock.close()
        offered_hash = hashlib.sha256(offered.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(offered_hash, ORACLE_REPLAY_SECRET_SHA256):
            _stamp_replay(False, "replay_denied: invalid or absent secret")
            return
        if deterministic_clock.manifest().get("calls"):
            _stamp_replay(False, "replay_denied: live session already made tool calls")
            return
        from raven_ar9 import _oracle_replay

        payload = _oracle_replay.run_mode("oracle")
        with lock:
            if state.get("done"):
                return
            eventlog = Path(os.environ.get("RAVEN_EVENTLOG_OUT", DEFAULT_EVENTLOG))
            _oracle_replay._write(eventlog, payload)
            if payload.get("appstate") is not None:
                appstate_path.parent.mkdir(parents=True, exist_ok=True)
                appstate_path.write_text(
                    json.dumps(payload["appstate"], default=str), encoding="utf-8"
                )
            state["done"] = True
        _stamp_replay(True, "oracle reference replay")
        AUTHORITY_FROZEN.set()
        return

    threading.Thread(target=_listen, daemon=True).start()


def _start_trigger_watcher(
    env: Any,
    deterministic_clock: DeterministicClock,
    lock: threading.RLock,
    state: dict[str, Any],
    apps: Any,
    appstate_path: Path,
) -> None:
    def _write_done(verdict: str) -> None:
        try:
            TRIGGER_DONE.parent.mkdir(parents=True, exist_ok=True)
            tmp = TRIGGER_DONE.with_suffix(TRIGGER_DONE.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(verdict)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, TRIGGER_DONE)
        except OSError:
            pass

    def _watch() -> None:
        while True:
            if not TRIGGER_REQUEST.exists():
                time.sleep(0.5)
                continue
            try:
                offered = TRIGGER_REQUEST.read_text(encoding="utf-8").strip()
            except OSError:
                time.sleep(0.5)
                continue
            try:
                TRIGGER_REQUEST.unlink()
            except OSError:
                pass
            offered_hash = hashlib.sha256(offered.encode("utf-8")).hexdigest()
            if not hmac.compare_digest(offered_hash, ORACLE_REPLAY_SECRET_SHA256):
                _stamp_replay(False, "replay_denied: invalid or absent secret")
                _write_done("refused: bad secret\n")
                return
            if deterministic_clock.manifest().get("calls"):
                _stamp_replay(False, "replay_denied: live session already made tool calls")
                _write_done("refused: live session already acted\n")
                return
            from raven_ar9 import _oracle_replay

            with lock:
                if state.get("done"):
                    return
                _oracle_replay.replay_to_authority()
                _stamp_replay(True, "oracle reference replay via trigger")
                state["done"] = True
                AUTHORITY_FROZEN.set()
            _write_done("ok\n")
            return

    threading.Thread(target=_watch, daemon=True).start()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    scenario, env, deterministic_clock, table = prepare()

    if args.list_tools:
        return _list_tools(table)

    apps = resolve_apps(scenario)
    appstate_path = _appstate_path()
    lock = threading.RLock()
    state: dict[str, Any] = {"done": False}

    def _on_signal(signum: int, frame: Any) -> None:
        flush(env, deterministic_clock, lock, state, apps=apps, appstate=appstate_path)
        os._exit(0)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # Defect 4 (durable event log independent of the collect SIGTERM): collect.py SIGTERMs this
    # server (PID 1); the _on_signal flush then races container death and can be killed before the
    # artifact lands (exit 137). A daemon thread continuously snapshots the event log to the
    # authoritative path, so the last snapshot is already on disk when collect reads it even if the
    # teardown flush loses the race. Non-destructive: it serializes without stopping the env.
    def _snapshot_loop() -> None:
        target = Path(os.environ.get("RAVEN_EVENTLOG_OUT", DEFAULT_EVENTLOG))
        while not state.get("done"):
            if AUTHORITY_FROZEN.is_set():
                return
            try:
                with lock:
                    if state.get("done"):
                        break
                    payload = _serialize(env)
                    payload.setdefault("event_log", {}).setdefault("past_events", [])
                    if deterministic_clock is not None:
                        payload["clock"] = deterministic_clock.manifest()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    tmp = target.with_suffix(target.suffix + ".snap")
                    tmp.write_text(json.dumps(payload), encoding="utf-8")
                    os.replace(tmp, target)
                    snapshot = _capture_appstate(apps)
                    if snapshot is not None:
                        statedump.write_appstate_atomic(snapshot, appstate_path)
            except Exception:  # noqa: BLE001 - best-effort snapshot; the authoritative flush still runs
                pass
            time.sleep(2.0)

    snapshot = threading.Thread(target=_snapshot_loop, daemon=True)
    snapshot.start()

    _start_oracle_replay_listener(env, deterministic_clock, lock, state, apps, appstate_path)
    _start_trigger_watcher(env, deterministic_clock, lock, state, apps, appstate_path)

    server = create_mcp_server(SERVER_NAME)
    register_surface(server, table, deterministic_clock)
    try:
        server.run(args.transport)
    finally:
        flush(env, deterministic_clock, lock, state, apps=apps, appstate=appstate_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
