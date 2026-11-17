"""Oracle-side trusted app-state snapshot for the raven-ar9 transit-recovery verifier.

TRUSTED BOUNDARY:

* This is a collect-time ORACLE routine, never an MCP tool. Nothing here is decorated
  ``@app_tool`` or registered on the published surface; ``get_state``/``dump_state``/
  ``load_state`` are already on ``mcp_surface.refusal_reason``'s block-list.
* The dump is produced on the oracle's own filesystem and written to an oracle-only
  absolute path (``/authority/appstate.json``) alongside the authoritative event log.
* The write is atomic (temp + ``os.replace``) and fail-closed: a valid JSON object or
  nothing at all, so ``tests/score.py::load_state`` never sees a torn file.

Shape consumed by ``tests/score.py`` (``Episode._state_section(app, key)`` reads
``state[app][key]``)::

    {
      "<AppName>": <app.get_state()>,
      "Files": { ...get_state()..., "contents": { "<path>": "<utf-8 text>", ... } },
      ...
    }

``Files.get_state()`` is names-only, yet the scorer parses the four seeded reference
documents (transfer times, hotel policy, travel policy, passport scan) for their TEXT.
This routine injects ``Files["contents"]`` by reading each reference document's bytes
through the Files app's own ``cat``. Every other app section (Calendar.events,
CabApp.ride_history, ShoppingApp.orders, Messages/Chats.conversations,
AgentUserInterface.messages) the scorer can project from the AGENT write events, so a
dump carrying app states plus ``Files.contents`` is sufficient and correct.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

FILES_APP_NAME = "Files"
CONTENTS_KEY = "contents"

# The four seeded reference docs the grader reads; mirrors tests/score.py::REFERENCE_DOCS.
_REFERENCE_DOC_PATHS = (
    "/trip/transfer_times.md",
    "/trip/hotel_policy.md",
    "/trip/travel_policy.md",
    "/trip/passport_scan.md",
)


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


def _decode(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).decode("utf-8", "replace")
    return str(raw)


def _cat(files_app: Any, path: str) -> str | None:
    for method in ("cat", "read_file", "read"):
        fn = getattr(files_app, method, None)
        if not callable(fn):
            continue
        try:
            return _decode(fn(path))
        except Exception:  # noqa: BLE001 - a missing file or wrong signature is not fatal
            continue
    return None


def contents_from_files_app(files_app: Any, paths: tuple[str, ...] = _REFERENCE_DOC_PATHS) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in paths:
        text = _cat(files_app, path)
        if text is not None:
            out[str(path)] = text
    return out


def build_appstate(
    apps: list[Any] | tuple[Any, ...] | None,
    extra_files_contents: dict[str, str] | None = None,
) -> dict[str, Any]:
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
                files_contents.update(contents_from_files_app(app))
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
    """Build the dump and write it atomically. Returns False (writes nothing) if empty."""
    payload = build_appstate(apps)
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
            super().__init__("Files", {"files": {}, "tmpdir": "/tmp/x"})
            self._docs = docs

        def cat(self, path: str) -> str:
            return self._docs[path]

    names = [
        "AgentUserInterface", "Files", "ContactsApp", "InternalContacts", "Messages",
        "Chats", "Emails", "Calendar", "RentAFlat", "CityApp", "CabApp", "ShoppingApp",
    ]
    policy_text = "# Wayfarer travel policy\nThe rebooking cap is EUR 400.\n"
    apps: list[Any] = []
    for name in names:
        if name == "Files":
            apps.append(_StubFiles({"/trip/travel_policy.md": policy_text}))
        else:
            apps.append(_StubApp(name, {"ok": True}))

    dump = build_appstate(apps)
    assert set(dump) == set(names), f"missing apps: {set(names) - set(dump)}"
    contents = dump["Files"][CONTENTS_KEY]
    assert contents.get("/trip/travel_policy.md") == policy_text, "Files contents missing policy text"

    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "are_appstate.json"
        assert write_appstate_atomic(dump, target) and target.exists(), "atomic write failed"
        assert not target.with_suffix(".json.tmp").exists(), "temp file left behind"
        bad = Path(d) / "bad.json"
        assert write_appstate_atomic(["not", "an", "object"], bad) is False
        assert not bad.exists(), "fail-closed violated"

    print("raven-ar9 statedump self-test: OK (shape, Files.contents, atomic, fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
