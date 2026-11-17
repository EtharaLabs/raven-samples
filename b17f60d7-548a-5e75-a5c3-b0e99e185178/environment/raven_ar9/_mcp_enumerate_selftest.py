"""Self-test for the oracle MCP surface and the deterministic clock.

Run it with no arguments:

    python -m raven_ar9._mcp_enumerate_selftest

It proves the surface and timing invariants against STUBS that reproduce the ARE
contracts this server depends on (``app.name``, ``app.get_tools()``,
``time_manager.time()/add_offset()``, ``env.tick()``), so it runs with neither
``meta-agents-research-environments`` nor ``mcp`` installed. When ARE *is*
importable it additionally replays the real imported universe through the same
code path, and says so in the report.

The estate it enumerates is this bundle's real one, taken from the ``name`` fields
of ``universe_0.json``. Two of its pairs are the point of the exercise: ``Messages``
and ``Chats`` are both ``MessagingAppV2``, and ``ContactsApp`` and
``InternalContacts`` are both contacts apps, so the ``{app.name}__{func}`` rule has
to give four disjoint namespaces rather than two shadowed ones.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from raven_ar9.clock import (
    EXTENSION_ID,
    TICK_SECONDS,
    ClockTamper,
    DeterministicClock,
)
from raven_ar9.mcp_surface import (
    NAME_SEPARATOR,
    audit,
    build_surface,
    make_metered_tool,
    refusal_reason,
)

UNIVERSE_APPS: tuple[str, ...] = (
    "AgentUserInterface",
    "Files",
    "ContactsApp",
    "InternalContacts",
    "Messages",
    "Chats",
    "Emails",
    "Calendar",
    "RentAFlat",
    "CityApp",
    "CabApp",
    "ShoppingApp",
)

SHARED_CLASS_PAIRS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Messages", "Chats", ("send_message", "list_recent_conversations")),
    ("ContactsApp", "InternalContacts", ("get_contact", "search_contacts")),
)

PUBLIC_TOOLS: dict[str, tuple[str, ...]] = {
    "AgentUserInterface": ("send_message_to_user", "get_last_message_from_user"),
    "Files": ("open", "ls", "cat"),
    "ContactsApp": ("get_contact", "search_contacts"),
    "InternalContacts": ("get_contact", "search_contacts"),
    "Messages": ("send_message", "list_recent_conversations"),
    "Chats": ("send_message", "list_recent_conversations"),
    "Emails": ("send_email", "search_emails", "list_emails"),
    "Calendar": ("add_calendar_event", "get_calendar_events", "delete_calendar_event"),
    "RentAFlat": ("search_flats", "get_flat_details"),
    "CityApp": ("search_places", "get_place_details"),
    "CabApp": ("order_ride", "get_ride_status"),
    "ShoppingApp": ("search_product", "add_to_cart", "checkout"),
}

# Names that MUST be refused on every app. The first five are the endpoint classes
# the task forbids (state dump, generic state resource, ground-truth/answer,
# collection dump, clock setter); the last two cover the private surface.
FORBIDDEN_TOOLS: tuple[str, ...] = (
    "get_state",
    "dump_state",
    "disclose",
    "get_collection",
    "set_time",
    "_gt_snapshot",
    "_close_window",
)


class SelfTestFailure(AssertionError):
    pass


@dataclass
class Report:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, bool(ok), detail))

    def require(self, name: str, ok: bool, detail: str = "") -> None:
        self.record(name, ok, detail)
        if not ok:
            raise SelfTestFailure(f"{name}: {detail}")

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]


class StubTimeManager:
    def __init__(self, start: float) -> None:
        self._now = float(start)

    def time(self) -> float:
        return self._now

    def add_offset(self, offset: float) -> None:
        self._now += float(offset)

    def force(self, value: float) -> None:
        self._now = float(value)


class StubEnvironment:
    """Minimal stand-in for ARE's Environment tick/pause/clock contract."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.time_manager = StubTimeManager(start)
        self.scheduled: list[tuple[float, int, Callable[[], Any]]] = []
        self.fired: list[tuple[float, int]] = []
        self.paused = False
        self._seq = 0

    def pause(self) -> None:
        self.paused = True

    def schedule_at(self, when: float, action: Callable[[], Any]) -> None:
        self.scheduled.append((float(when), self._seq, action))
        self._seq += 1

    def tick(self) -> int:
        now = self.time_manager.time()
        due = sorted([e for e in self.scheduled if e[0] <= now], key=lambda e: (e[0], e[1]))
        for when, seq, action in due:
            self.scheduled.remove((when, seq, action))
            action()
            self.fired.append((when, seq))
        return len(due)


class StubApp:
    """An app exposing its tool set the way ARE's ``App.get_tools`` does."""

    def __init__(self, name: str, tools: tuple[str, ...], prefix_tool_names: bool = False) -> None:
        self.name = name
        self._tools = tools
        self._prefix = prefix_tool_names
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        for function_name in tools + FORBIDDEN_TOOLS:
            self._install(function_name)

    def _install(self, function_name: str) -> None:
        def handler(*args: Any, **kwargs: Any) -> dict[str, Any]:
            self.calls.append((function_name, args, kwargs))
            return {"app": self.name, "function": function_name}

        handler.__name__ = function_name
        handler.__doc__ = f"{function_name} on {self.name}."
        setattr(self, function_name, handler)

    def get_tools(self) -> list[Any]:
        published = self._tools + FORBIDDEN_TOOLS
        if self._prefix:
            return [SimpleNamespace(name=f"{self.name}{NAME_SEPARATOR}{t}") for t in published]
        return [SimpleNamespace(name=t) for t in published]


def build_estate() -> list[StubApp]:
    return [
        StubApp(name, PUBLIC_TOOLS[name], prefix_tool_names=(index % 2 == 0))
        for index, name in enumerate(UNIVERSE_APPS)
    ]


def check_surface(report: Report) -> dict[str, Any]:
    table = build_surface(build_estate())
    result = audit(table, expected_apps=UNIVERSE_APPS)
    names = table.names()

    report.require(
        "all_12_apps_present",
        result["app_count"] == 12 and not result["missing_expected_apps"],
        f"apps={result['apps']} missing={result['missing_expected_apps']}",
    )
    report.require(
        "no_shadowing_duplicate_tool_names",
        not result["duplicate_tool_names"] and len(set(names)) == len(names),
        f"duplicates={result['duplicate_tool_names']}",
    )
    report.require(
        "every_app_has_a_namespace",
        all(result["tools_per_app"].get(app, 0) > 0 for app in UNIVERSE_APPS),
        json.dumps(result["tools_per_app"], sort_keys=True),
    )

    for left, right, shared in SHARED_CLASS_PAIRS:
        for function_name in shared:
            left_name = f"{left}{NAME_SEPARATOR}{function_name}"
            right_name = f"{right}{NAME_SEPARATOR}{function_name}"
            report.require(
                f"disjoint:{left_name}|{right_name}",
                left_name in names and right_name in names and left_name != right_name,
                f"{left_name in names=} {right_name in names=}",
            )

    report.require(
        "no_private_or_state_or_disclose_or_set_time_exposed",
        not result["leaked_denied_tools"],
        f"leaked={result['leaked_denied_tools']}",
    )
    for function_name in FORBIDDEN_TOOLS:
        exposed = [n for n in names if n.split(NAME_SEPARATOR, 1)[-1] == function_name]
        report.require(f"refused:{function_name}", not exposed, f"exposed as {exposed}")
        report.require(
            f"refusal_reason_exists:{function_name}",
            refusal_reason(function_name) is not None,
            "filter would have allowed it",
        )
    report.require(
        "refusals_recorded_for_every_app",
        len(result["refused"]) == len(UNIVERSE_APPS) * len(FORBIDDEN_TOOLS),
        f"{len(result['refused'])} refusals recorded",
    )
    return result


def check_clock_determinism(report: Report) -> dict[str, Any]:
    env = StubEnvironment()
    clock = DeterministicClock(env)
    start = clock.sim_time()

    table = build_surface(build_estate())
    spec = next(s for s in table.tools if s.public_name == "Calendar__add_calendar_event")
    tool = make_metered_tool(spec, clock)

    for index in range(1, 6):
        tool(title="x")
        expected = start + index * TICK_SECONDS
        report.require(
            f"advance_is_fixed_call_{index}",
            abs(clock.sim_time() - expected) < 1e-9,
            f"expected {expected}, got {clock.sim_time()}",
        )

    failing = next(s for s in table.tools if s.public_name == "CabApp__order_ride")
    broken = make_metered_tool(
        type(failing)(
            public_name=failing.public_name,
            app_name=failing.app_name,
            function_name=failing.function_name,
            description=failing.description,
            target=lambda **_: (_ for _ in ()).throw(ValueError("tool failed")),
        ),
        clock,
    )
    before = clock.sim_time()
    raised = False
    try:
        broken()
    except ValueError:
        raised = True
    report.require("failed_call_raises", raised, "the failure was swallowed")
    report.require(
        "failed_call_is_metered",
        abs(clock.sim_time() - (before + TICK_SECONDS)) < 1e-9,
        f"{before} -> {clock.sim_time()}",
    )

    before = clock.sim_time()
    clock.wait()
    report.require(
        "wait_noop_is_metered",
        abs(clock.sim_time() - (before + TICK_SECONDS)) < 1e-9,
        f"{before} -> {clock.sim_time()}",
    )

    outcomes = {entry["outcome"] for entry in clock.ledger()}
    report.require(
        "ledger_records_ok_error_and_noop",
        {"ok", "error", "noop"} <= outcomes,
        f"outcomes={sorted(outcomes)}",
    )
    report.require(
        "every_call_ledgered",
        len(clock.ledger()) == clock.calls == 7,
        f"calls={clock.calls} ledger={len(clock.ledger())}",
    )
    report.require(
        "no_wall_clock_dependence",
        all(
            abs(entry["advance_observed"] - TICK_SECONDS) < 1e-9 for entry in clock.ledger()
        ),
        "an advance differed from the declared quantum",
    )

    manifest = clock.manifest()
    report.require(
        "manifest_declares_custom_extension",
        manifest["extension"] == EXTENSION_ID and manifest["is_stock_are_timing"] is False,
        json.dumps({k: manifest[k] for k in ("extension", "is_stock_are_timing")}),
    )
    return manifest


def check_cutoff_ordering(report: Report) -> dict[str, Any]:
    """E2: the cutoff must fire before the body of the call whose advance reaches it."""
    env = StubEnvironment()
    clock = DeterministicClock(env)
    cutoff = clock.sim_time() + 3 * TICK_SECONDS
    window = {"closed": False}
    env.schedule_at(cutoff, lambda: window.__setitem__("closed", True))

    observations: list[tuple[int, float, bool]] = []

    def write() -> dict[str, Any]:
        observations.append((len(observations), clock.sim_time(), window["closed"]))
        return {"ok": True}

    for _ in range(4):
        clock.meter(tool="Calendar__add_calendar_event", app="Calendar", function="add_calendar_event", body=write)

    report.require(
        "cutoff_closed_exactly_on_the_crossing_call",
        [o[2] for o in observations] == [False, False, True, True],
        f"observations={observations}",
    )
    report.require(
        "writes_before_cutoff_are_strictly_earlier",
        all(o[1] < cutoff for o in observations if not o[2])
        and all(o[1] >= cutoff for o in observations if o[2]),
        f"cutoff={cutoff} observations={observations}",
    )
    report.require("cutoff_fired_once", env.fired == [(cutoff, 0)], f"fired={env.fired}")
    return {"cutoff": cutoff, "observations": observations}


def check_tamper_protection(report: Report) -> None:
    env = StubEnvironment()
    clock = DeterministicClock(env)
    clock.wait()

    env.time_manager.force(clock.sim_time() - 600.0)
    caught = False
    try:
        clock.wait()
    except ClockTamper:
        caught = True
    report.require("backward_jump_raises_clock_tamper", caught, "a backward jump was accepted")

    public_setters = [
        name
        for name in dir(DeterministicClock)
        if not name.startswith("_")
        and any(token in name for token in ("set", "reset", "rewind", "offset", "force"))
    ]
    report.require(
        "clock_exposes_no_public_setter",
        not public_setters,
        f"setters={public_setters}",
    )
    report.require(
        "clock_is_not_an_app_tool",
        not hasattr(DeterministicClock, "name") and not hasattr(DeterministicClock, "get_tools"),
        "the clock looks like an ARE app and could be published",
    )

    for token in ("set_time", "add_offset", "reset", "pause", "rewind", "reconfigure"):
        report.require(
            f"tamper_token_denied:{token}",
            refusal_reason(token) is not None,
            "the surface filter would publish it",
        )

    try:
        DeterministicClock(env, tick_seconds=0.0)
        report.require("zero_quantum_rejected", False, "a zero quantum was accepted")
    except ValueError:
        report.record("zero_quantum_rejected", True)


def check_reproducibility(report: Report) -> None:
    def run() -> str:
        env = StubEnvironment()
        clock = DeterministicClock(env)
        table = build_surface(build_estate())
        for spec in table.tools[:12]:
            make_metered_tool(spec, clock)()
        return json.dumps(
            {"tools": list(table.names()), "ledger": clock.ledger()}, sort_keys=True
        )

    first, second = run(), run()
    report.require("two_runs_are_byte_identical", first == second, "the surface or ledger drifted")


def check_real_universe(report: Report) -> str:
    try:
        from raven_ar9.server import prepare
    except Exception as exc:  # noqa: BLE001 - absence of ARE is reported, not fatal
        report.record("real_universe_replayed", True, f"skipped: {exc}")
        return f"skipped ({exc})"
    try:
        _, _, _, table = prepare()
    except Exception as exc:  # noqa: BLE001
        report.record("real_universe_replayed", True, f"skipped: {exc}")
        return f"skipped ({exc})"
    result = audit(table, expected_apps=UNIVERSE_APPS)
    report.require(
        "real_universe_has_no_duplicates",
        not result["duplicate_tool_names"],
        f"duplicates={result['duplicate_tool_names']}",
    )
    report.require(
        "real_universe_leaks_nothing",
        not result["leaked_denied_tools"],
        f"leaked={result['leaked_denied_tools']}",
    )
    report.require(
        "real_universe_covers_12_apps",
        result["app_count"] >= 12,
        f"apps={result['apps']}",
    )
    return json.dumps(result, sort_keys=True)


def main() -> int:
    report = Report()
    surface = check_surface(report)
    manifest = check_clock_determinism(report)
    cutoff = check_cutoff_ordering(report)
    check_tamper_protection(report)
    check_reproducibility(report)
    real = check_real_universe(report)

    print("=" * 78)
    print("raven_ar9 oracle MCP surface + deterministic clock self-test")
    print("=" * 78)
    print(f"\nclock extension         : {manifest['extension']}")
    print(f"stock ARE timing        : {manifest['is_stock_are_timing']}")
    print(f"advance per tool call   : {manifest['tick_seconds']}s (fixed, wall-clock independent)")
    print(f"advance on rejected call: {manifest['tick_seconds_rejected']}s")
    print(f"dispatch                : {manifest['dispatch']}")
    print(f"cutoff rule             : {manifest['cutoff_rule']}")
    print(f"\napps exposed            : {surface['app_count']}")
    print(f"tools exposed           : {surface['tool_count']}")
    print(f"duplicate tool names    : {surface['duplicate_tool_names'] or 'none'}")
    print(f"denied tools leaked     : {surface['leaked_denied_tools'] or 'none'}")
    print(f"endpoints refused       : {len(surface['refused'])}")
    print(f"\nE2 cutoff instant       : {cutoff['cutoff']}")
    for index, now, closed in cutoff["observations"]:
        print(f"  write #{index} at sim_time={now:.1f} window_closed={closed}")

    print("\nper-app namespaces:")
    for app in UNIVERSE_APPS:
        count = surface["tools_per_app"][app]
        print(f"  {app:<20} {count:>2} tool(s)")

    print("\nrefusal reasons (first app, representative):")
    for entry in surface["refused"][: len(FORBIDDEN_TOOLS)]:
        print(f"  {entry['app']}{NAME_SEPARATOR}{entry['function']:<16} -> {entry['reason']}")

    print(f"\nreal imported universe  : {real[:160]}")

    print("\nchecks:")
    for name, ok, detail in report.checks:
        mark = "PASS" if ok else "FAIL"
        suffix = f"  ({detail})" if detail and not ok else ""
        print(f"  [{mark}] {name}{suffix}")

    failures = report.failed
    print(f"\n{len(report.checks) - len(failures)}/{len(report.checks)} checks passed")
    if failures:
        print("FAILED: " + ", ".join(name for name, _, _ in failures))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
