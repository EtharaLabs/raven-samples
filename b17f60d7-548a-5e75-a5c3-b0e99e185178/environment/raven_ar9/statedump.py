"""Oracle-side trusted app-state snapshot for the raven-ar9 verifier (GAP 2).

TRUSTED BOUNDARY:

* This is a **collect-time ORACLE routine, never an MCP tool**. Nothing here is
  decorated ``@app_tool`` or registered on the published surface; the function
  names (``get_state``/``dump_state``/``load_state``) are already on
  ``mcp_surface.refusal_reason``'s block-list, so even a probe for them is refused.
  The agent container has no engine source and no path to this module.
* The dump is produced on the **oracle's own filesystem** and written to an
  oracle-only absolute path (``/authority/appstate.json``) ALONGSIDE the
  authoritative event log (``/authority/eventlog.json``). No agent-writable
  path maps there (``environment/docker-compose.yaml``: ``oracle-authority`` is
  oracle-only).
* The write is **atomic** (temp + ``os.replace``) and **fail-closed**: this module
  writes a valid JSON object or nothing at all, never a partial/corrupt file.
  ``tests/score.py::load_state`` raises ``HarnessFault`` on an unreadable or
  non-object dump, so a torn write would fail the harness loudly; validating the
  payload before the rename is what prevents that.

Shape consumed by ``tests/score.py`` (``Episode._state_section(app, key)`` reads
``state[app][key]``)::

    {
      "<AppName>": <app.get_state()>,            # one entry per native universe app
      "Files": { ...get_state()..., "contents": { "<path>": "<utf-8 text>", ... } },
      ...
    }

``Files.get_state()`` is **names-only** (``{"files": <tree>, "tmpdir": str}``), yet
the agenda predicates (``o10_written``/``o10_complete``) need the document TEXT,
which lives only in final state or the O8 delivery payload. This routine injects
``Files["contents"]`` by reading each in-episode document's bytes through the Files
app's own ``cat`` (or, at teardown, from the real sandbox tmpdir on disk). That is
the one load-bearing value the event-log projection in ``Episode`` cannot recover;
every other app section the scorer reads (Calendar.events, CabApp.ride_history,
Messages/Chats.conversations, AgentUserInterface.messages) it can project from the
AGENT write events, so a dump that carries ONLY ``Files.contents`` is already
sufficient and correct — the scorer degrades the rest gracefully.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# Fixed per-episode constant; must equal tests/score.py::AGENDA_PATH (INTERFACES O7).
AGENDA_PATH = "/Documents/client_review_agenda.md"
FILES_APP_NAME = "Files"
CONTENTS_KEY = "contents"

# Files get_state() returns a {name,type,children} tree that the generic tree-walk cannot
# resolve to document bodies, so the four reference docs the grader needs are read by absolute
# path (mirrors score.py::REFERENCE_DOCS).
_REFERENCE_DOC_PATHS = (
    "/Work/facilities/rooms.md",
    "/Work/facilities/procurement_rules.md",
    "/Work/facilities/travel_times.md",
    "/Work/minutes/2024-10-03-telemetry-review-minutes.md",
)

# Must mirror tests/score.py::WRITE_MODES.
_WRITE_MODES = ("w", "wb", "w+", "wt", "a", "ab")

# ARE per-run sandbox dir prefix (INTERFACES section 4, Files.open return_value).
_SANDBOX_GLOB = "are_simulation_fs_sandbox_*"


def _app_name(app: Any) -> str:
    return str(getattr(app, "name", None) or type(app).__name__)


def _safe_get_state(app: Any) -> Any:
    state = app.get_state()
    if isinstance(state, str):
        try:
            return json.loads(state)
        except ValueError:
            return state
    return state


def _iter_document_paths(files_state: Any) -> list[str]:
    """Best-effort list of document paths from a Files get_state() tree.

    ARE's SandboxLocalFileSystem renders ``files`` as a nested name tree; we only need
    whatever paths we can confidently reconstruct, plus the fixed AGENDA_PATH, which is
    always attempted explicitly. Unknown tree shapes degrade to just AGENDA_PATH.
    """
    paths: list[str] = []

    def _walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for name, child in node.items():
                child_path = f"{prefix.rstrip('/')}/{name}"
                if isinstance(child, (dict, list)) and child:
                    _walk(child, child_path)
                else:
                    paths.append(child_path)
        elif isinstance(node, list):
            for name in node:
                paths.append(f"{prefix.rstrip('/')}/{name}")

    if isinstance(files_state, dict):
        tree = files_state.get("files")
        if isinstance(tree, (dict, list)):
            _walk(tree, "/")
    if AGENDA_PATH not in paths:
        paths.append(AGENDA_PATH)
    return paths


def _decode(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).decode("utf-8", "replace")
    return str(raw)


def _cat(files_app: Any, path: str) -> str | None:
    """Read one document's text through the Files app's public read API."""
    for method in ("cat", "read_file", "read"):
        fn = getattr(files_app, method, None)
        if not callable(fn):
            continue
        try:
            return _decode(fn(path))
        except Exception:  # noqa: BLE001 - a missing file or wrong signature is not fatal
            continue
    return None


def contents_from_files_app(files_app: Any, extra_paths: tuple[str, ...] = ()) -> dict[str, str]:
    """``{path: utf-8 text}`` for every readable in-episode document, incl. AGENDA_PATH."""
    try:
        state = _safe_get_state(files_app)
    except Exception:  # noqa: BLE001 - fall back to just the known paths
        state = None
    paths = list(dict.fromkeys(_iter_document_paths(state) + list(extra_paths)))
    out: dict[str, str] = {}
    for path in paths:
        text = _cat(files_app, path)
        if text is not None:
            out[str(path)] = text
    return out


def contents_from_sandbox_dirs(roots: tuple[str, ...] = ()) -> dict[str, str]:
    """Recover agenda-document text from the per-run ARE sandbox dir(s) on disk.

    The agent's ``Files.open("/Documents/client_review_agenda.md", "w")`` lands in a
    real tmpdir ``<sandbox>/Documents/client_review_agenda.md`` (INTERFACES section 4).
    At teardown the live Files app is gone with the server process, but the real file
    may still be on the oracle fs; scanning the system temp root recovers it. Keyed by
    the stable sandbox-relative path so ``score.py`` matches it.
    """
    import glob
    import tempfile

    search_roots = list(roots) or [tempfile.gettempdir(), "/tmp"]
    rel = AGENDA_PATH.lstrip("/")
    out: dict[str, str] = {}
    seen: set[str] = set()
    for root in search_roots:
        if not root or root in seen or not os.path.isdir(root):
            continue
        seen.add(root)
        for sandbox in sorted(glob.glob(os.path.join(root, _SANDBOX_GLOB))):
            candidate = os.path.join(sandbox, rel)
            if os.path.isfile(candidate):
                try:
                    out[AGENDA_PATH] = Path(candidate).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
    return out


def contents_from_event_log(artifact: dict[str, Any]) -> dict[str, str]:
    """Recover agenda text from the real path embedded in a ``Files.open`` return_value.

    ``metadata.return_value`` of a ``Files.open`` write is the absolute on-disk handle
    path in the sandbox; reading it yields the document's final bytes. Only AGENT write
    opens to the agenda path are considered (baseline guard + INTERFACES O7).
    """
    inner = (artifact or {}).get("event_log") or {}
    entries = inner.get("past_events") or []
    out: dict[str, str] = {}
    for entry in entries:
        if entry.get("event_type") != "AGENT":
            continue
        action = entry.get("action") or {}
        if action.get("app_name") != FILES_APP_NAME or action.get("function_name") != "open":
            continue
        args = action.get("args") or {}
        path = str(args.get("path") or "")
        mode = str(args.get("mode") or "").lower()
        if not path.endswith(AGENDA_PATH.lstrip("/")) or mode not in _WRITE_MODES:
            continue
        real = (entry.get("metadata") or {}).get("return_value")
        if isinstance(real, str) and os.path.isfile(real):
            try:
                out[AGENDA_PATH] = Path(real).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out


def build_appstate(
    apps: list[Any] | tuple[Any, ...] | None,
    extra_files_contents: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the ``{<AppName>: get_state(), ...}`` dump, injecting ``Files.contents``.

    ``apps`` may be ``None`` (no live app set reachable at teardown) — then the dump
    carries only a synthetic ``Files`` section holding the recovered ``contents``,
    which is sufficient for the agenda predicates while the scorer projects every
    other app from the event log.
    """
    state: dict[str, Any] = {}
    files_contents: dict[str, str] = {}
    for app in apps or []:
        name = _app_name(app)
        try:
            section = _safe_get_state(app)
        except Exception:  # noqa: BLE001 - one app's get_state() must not void the whole dump
            continue
        state[name] = section
        if name == FILES_APP_NAME:
            try:
                files_contents.update(
                    contents_from_files_app(app, extra_paths=_REFERENCE_DOC_PATHS)
                )
            except Exception:  # noqa: BLE001 - Files content recovery is best-effort
                pass
    if extra_files_contents:
        files_contents.update({str(k): v for k, v in extra_files_contents.items() if v is not None})
    if files_contents:
        files_section = state.get(FILES_APP_NAME)
        if not isinstance(files_section, dict):
            files_section = {}
        existing = files_section.get(CONTENTS_KEY)
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged.update(files_contents)
        files_section[CONTENTS_KEY] = merged
        state[FILES_APP_NAME] = files_section
    return state


def _is_json_object(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    try:
        json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return False
    return True


def write_appstate_atomic(payload: dict[str, Any], target: str | os.PathLike[str]) -> bool:
    """Write ``payload`` atomically. Returns True on success, False (no file) on refusal.

    Fail-closed: a payload that is not a JSON object, or that fails to serialise, is
    REFUSED (nothing is written) so a downstream reader never sees a corrupt dump. The
    temp file lives in the target directory so ``os.replace`` is a same-filesystem
    rename (atomic). On any error the temp file is removed.
    """
    if not _is_json_object(payload):
        return False
    target_path = Path(target)
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, default=str, sort_keys=True)
    except (OSError, TypeError, ValueError):
        return False
    tmp = target_path.with_suffix(target_path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target_path)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False
    return True


def dump_appstate(
    target: str | os.PathLike[str],
    apps: list[Any] | tuple[Any, ...] | None = None,
    artifact: dict[str, Any] | None = None,
    sandbox_roots: tuple[str, ...] = (),
) -> bool:
    """Full oracle-side routine: recover Files contents, build the dump, write it atomically.

    Recovery order for the agenda document (first readable wins, log is most trusted):
    the real path in the event log's ``Files.open`` return_value, then an on-disk
    sandbox scan, then (if a live Files app is in ``apps``) its ``cat``. Writes nothing
    and returns False when no content and no app set are available, so the scorer falls
    back to its event-log projection + O8 delivery payload rather than reading a partial
    dump.
    """
    recovered: dict[str, str] = {}
    if artifact is not None:
        recovered.update(contents_from_event_log(artifact))
    if AGENDA_PATH not in recovered:
        recovered.update(contents_from_sandbox_dirs(sandbox_roots))
    payload = build_appstate(apps, extra_files_contents=recovered)
    if not payload:
        return False
    return write_appstate_atomic(payload, target)


def _selftest() -> int:
    import tempfile

    class _StubApp:
        def __init__(self, name: str, state: dict[str, Any]) -> None:
            self.name = name
            self._state = state

        def get_state(self) -> dict[str, Any]:
            return self._state

    class _StubFiles(_StubApp):
        def __init__(self, docs: dict[str, str]) -> None:
            super().__init__("Files", {"files": {"Documents": list(_leaf(p) for p in docs)}, "tmpdir": "/tmp/x"})
            self._docs = docs

        def cat(self, path: str) -> str:
            return self._docs[path]

    def _leaf(path: str) -> str:
        return path.rsplit("/", 1)[-1]

    names = [
        "AgentUserInterface", "Files", "ContactsApp", "InternalContacts", "Messages",
        "Chats", "Emails", "Calendar", "RentAFlat", "CityApp", "CabApp", "ShoppingApp",
    ]
    agenda_text = (
        "# Client Review\n\n## Agenda\n\n"
        "1. Flood gauge telemetry backlog\n2. Q4 abstraction licence renewals\n"
        "3. Hydrometric data retention policy\n"
    )
    apps: list[Any] = []
    for name in names:
        if name == "Files":
            apps.append(_StubFiles({AGENDA_PATH: agenda_text}))
        elif name == "Calendar":
            apps.append(_StubApp(name, {"events": {}}))
        elif name == "CabApp":
            apps.append(_StubApp(name, {"ride_history": []}))
        else:
            apps.append(_StubApp(name, {"ok": True}))

    dump = build_appstate(apps)
    assert set(dump) == set(names), f"missing apps: {set(names) - set(dump)}"
    contents = dump["Files"][CONTENTS_KEY]
    assert contents.get(AGENDA_PATH) == agenda_text, "Files contents missing agenda text"
    assert "telemetry backlog" in contents[AGENDA_PATH].lower()

    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "are_appstate.json"
        ok = write_appstate_atomic(dump, target)
        assert ok and target.exists(), "atomic write failed"
        assert not target.with_suffix(".json.tmp").exists(), "temp file left behind"
        reloaded = json.loads(target.read_text(encoding="utf-8"))
        assert reloaded["Files"][CONTENTS_KEY][AGENDA_PATH] == agenda_text, "round-trip mismatch"

        bad_target = Path(d) / "bad.json"
        assert write_appstate_atomic(["not", "an", "object"], bad_target) is False
        assert not bad_target.exists(), "fail-closed violated: wrote a non-object"

        files_only = build_appstate(None, extra_files_contents={AGENDA_PATH: agenda_text})
        assert files_only["Files"][CONTENTS_KEY][AGENDA_PATH] == agenda_text

    print("raven-ar9 statedump self-test: OK (shape, Files.contents, atomic, fail-closed)")
    return 0


assert re.match(r"^/", AGENDA_PATH)


if __name__ == "__main__":
    raise SystemExit(_selftest())
