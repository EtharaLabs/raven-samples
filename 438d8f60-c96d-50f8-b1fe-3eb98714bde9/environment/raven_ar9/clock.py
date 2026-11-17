"""Deterministic per-tool simulation clock for the raven-ar9 oracle MCP server.

THIS IS A DECLARED CUSTOM EXTENSION, NOT STOCK ARE BEHAVIOUR.
=============================================================
The stock ``meta-agents-research-environments`` gaia2 live MCP sidecar advances the
simulated clock by the REAL WALL-CLOCK LATENCY of each tool call (capped at 300s)
through ``env.time_manager.add_offset(latency)`` followed by ``env.tick()``. That is
bespoke sidecar code, not an ARE policy, and it makes sim time a function of model
speed, network jitter and host load. For a graded temporal-deadline task that is a
LEVER: a faster model gets more simulated budget for the same work.

This module replaces that with a FIXED, wall-clock-independent quantum. It is the
sole authority over simulated time inside the server process. No MCP tool can set,
reset, rewind, pause or bypass it, and there is no unmetered call path.

The timing contract this file implements is also mirrored by the scorer
(``tests/score.py``), which reads the ``clock`` block from the collected event log.

Design
------
Per agent tool call, in this exact order (single-threaded, one call at a time):

    1. ADVANCE   sim_time += TICK_SECONDS                (unconditional, pre-body)
    2. TICK      fire every event with event_time <= sim_time, in deterministic order
    3. BODY      execute the app tool (may raise)
    4. SETTLE    tick again, to absorb any offset the app body declared itself

Step 1 happens BEFORE the body for every call, successful or not, so:

  * the cost of a call is paid before its effect is evaluated, and
  * a cutoff event scheduled at instant T (this bundle's E2) fires in step 2 of the
    first call whose advance reaches T, i.e. STRICTLY BEFORE that call's body runs.

That makes the cutoff boundary a property of the call index alone, which is what
lets Lane D's scorer and Lane A's E2 agree without either observing wall time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol

# One simulated minute of estate time per agent tool call. Deliberately a plain
# module constant with NO environment-variable override and NO setter: the quantum
# is part of the graded task definition, so a runtime knob would be a tamper
# surface. Changing it is an authoring edit to this file, reviewable in diff.
TICK_SECONDS: float = 60.0

# Advance applied when the dispatcher rejects a call before it ever reaches an app
# (unknown tool name, malformed arguments, denied endpoint). Equal to TICK_SECONDS
# on purpose: an invalid call is not a free call, so probing the surface with
# garbage is not a way to buy time.
TICK_SECONDS_REJECTED: float = TICK_SECONDS

EXTENSION_ID = "raven.deterministic_clock/v1"

# Function-name tokens that must never be reachable as an MCP tool because they
# would hand the agent the clock. ``mcp_surface`` imports this and refuses to
# publish any tool whose function name contains one of them. The first six are
# byte-identical to the scorer's own tamper scanner so the two agree on the
# vocabulary.
CLOCK_TAMPER_TOKENS: tuple[str, ...] = (
    "set_time",
    "reset",
    "rewind",
    "pause",
    "set_offset",
    "reconfigure",
    "add_offset",
    "set_clock",
    "settime",
    "time_manager",
    "resume",
    "fast_forward",
    "skip_ahead",
)

# Tolerance for float comparison on sim-time readings (seconds).
EPSILON = 1e-6


class ClockTamper(RuntimeError):
    """Raised when simulated time moved in a way the clock did not authorise.

    Fail-loud by design: a silently-swallowed backward jump would corrupt every
    timing judgement downstream, so the server surfaces this instead of guessing.
    """


class _TimeManagerLike(Protocol):
    def time(self) -> float: ...
    def add_offset(self, offset: float) -> Any: ...


class _EnvironmentLike(Protocol):
    time_manager: _TimeManagerLike

    def tick(self) -> Any: ...


@dataclass(frozen=True)
class CallStamp:
    """The timing record of one metered agent tool call.

    Field names here are the published contract; Lane D's scorer reads them from
    the event log's ``clock`` block.
    """

    call_index: int
    tool: str
    app: str
    function: str
    sim_time_before: float
    sim_time_after_advance: float
    sim_time_after: float
    advance_requested: float
    advance_observed: float
    app_declared_cost: float
    outcome: str
    events_fired_before_body: int
    events_fired_after_body: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "call_index": self.call_index,
            "tool": self.tool,
            "app": self.app,
            "function": self.function,
            "sim_time_before": self.sim_time_before,
            "sim_time_after_advance": self.sim_time_after_advance,
            "sim_time_after": self.sim_time_after,
            "advance_requested": self.advance_requested,
            "advance_observed": self.advance_observed,
            "app_declared_cost": self.app_declared_cost,
            "outcome": self.outcome,
            "events_fired_before_body": self.events_fired_before_body,
            "events_fired_after_body": self.events_fired_after_body,
        }


@dataclass
class DeterministicClock:
    """The single mutator of simulated time in the server process.

    Exposes no public setter. ``meter`` is the only method that moves the clock,
    and it always moves it by the declared quantum. Callers hold this object; the
    agent never does, because it is not an app and has no ``@app_tool``.
    """

    env: _EnvironmentLike
    tick_seconds: float = TICK_SECONDS
    _calls: int = 0
    _ledger: list[CallStamp] = field(default_factory=list)
    _start_time: float | None = None
    _last_reading: float | None = None

    def __post_init__(self) -> None:
        if not (isinstance(self.tick_seconds, (int, float)) and math.isfinite(self.tick_seconds)):
            raise ValueError(f"tick_seconds must be a finite number, got {self.tick_seconds!r}")
        if self.tick_seconds <= 0.0:
            raise ValueError(
                f"tick_seconds must be strictly positive so no call is unmetered, got {self.tick_seconds!r}"
            )
        self._start_time = self.sim_time()
        self._last_reading = self._start_time

    def sim_time(self) -> float:
        """The authoritative simulated instant, in the universe's epoch seconds."""
        return float(self.env.time_manager.time())

    @property
    def start_time(self) -> float:
        return float(self._start_time if self._start_time is not None else 0.0)

    @property
    def calls(self) -> int:
        return self._calls

    def ledger(self) -> list[dict[str, Any]]:
        return [stamp.as_dict() for stamp in self._ledger]

    def manifest(self) -> dict[str, Any]:
        """The self-describing timing block written into the collected event log."""
        return {
            "extension": EXTENSION_ID,
            "is_stock_are_timing": False,
            "advance_model": "fixed_quantum_per_tool_call",
            "tick_seconds": self.tick_seconds,
            "tick_seconds_rejected": TICK_SECONDS_REJECTED,
            "wall_clock_dependent": False,
            "meters_failed_calls": True,
            "dispatch": "single_threaded",
            "cutoff_rule": "events_due_at_or_before_sim_time_fire_before_the_body_of_the_call_that_reached_them",
            "start_time": self.start_time,
            "end_time": self.sim_time(),
            "calls": self._calls,
            "ledger": self.ledger(),
        }

    def meter(
        self,
        *,
        tool: str,
        app: str,
        function: str,
        body: Any = None,
        rejected: bool = False,
    ) -> tuple[Any, CallStamp]:
        """Advance, fire due events, run ``body``, settle, and record the stamp.

        ``body`` is a zero-argument callable or ``None`` for a pure wait/no-op.
        An exception from ``body`` is re-raised AFTER the stamp is recorded, so a
        failing call is metered exactly like a successful one.
        """
        before = self._guarded_reading()
        requested = TICK_SECONDS_REJECTED if rejected else self.tick_seconds

        self.env.time_manager.add_offset(requested)
        after_advance = self.sim_time()
        if after_advance < before + requested - EPSILON:
            raise ClockTamper(
                f"advance for {tool!r} did not take: {before} + {requested} -> {after_advance}"
            )
        fired_pre = self._tick()

        outcome = "rejected" if rejected else "ok"
        error: BaseException | None = None
        result: Any = None
        if body is not None:
            try:
                result = body()
            except BaseException as exc:  # noqa: BLE001 - metered, then re-raised
                outcome = "error"
                error = exc
        elif not rejected:
            outcome = "noop"

        fired_post = self._tick()
        after = self.sim_time()
        if after < after_advance - EPSILON:
            raise ClockTamper(
                f"simulated time moved backwards across {tool!r}: {after_advance} -> {after}"
            )

        stamp = CallStamp(
            call_index=self._calls,
            tool=tool,
            app=app,
            function=function,
            sim_time_before=before,
            sim_time_after_advance=after_advance,
            sim_time_after=after,
            advance_requested=requested,
            advance_observed=after - before,
            app_declared_cost=max(0.0, after - after_advance),
            outcome=outcome,
            events_fired_before_body=fired_pre,
            events_fired_after_body=fired_post,
        )
        self._calls += 1
        self._ledger.append(stamp)
        self._last_reading = after

        if error is not None:
            raise error
        return result, stamp

    def wait(self) -> CallStamp:
        """The explicit no-op path: advance one quantum and fire what comes due.

        This is what the dispatcher uses when a call carries no app body. It is the
        same metered path as a real call, so waiting costs exactly what acting costs
        and cannot be used to gain budget.
        """
        _, stamp = self.meter(tool="__wait__", app="__clock__", function="wait", body=None)
        return stamp

    def _guarded_reading(self) -> float:
        now = self.sim_time()
        if self._last_reading is not None and now < self._last_reading - EPSILON:
            raise ClockTamper(
                f"simulated time moved backwards between calls: {self._last_reading} -> {now}"
            )
        return now

    def _tick(self) -> int:
        """Fire every event due at or before the current instant.

        ARE's ``Environment.tick`` drains its scheduled-event queue in event-time
        order; dispatch is single-threaded, so the firing order for a given set of
        due events is fully determined by (event_time, schedule order). Returns the
        number of events the engine reported firing, or ``-1`` when the engine does
        not report a count (older ARE ``tick()`` returns ``None``).
        """
        fired = self.env.tick()
        if isinstance(fired, int):
            return fired
        if isinstance(fired, (list, tuple, set)):
            return len(fired)
        return -1


def pause_environment(env: Any) -> str:
    """Stop the engine's own time thread so this clock is the only time source.

    ARE's live sidecar does the same thing before it starts serving: the engine is
    started (so apps and events are wired) and then paused permanently, after which
    time only moves through ``add_offset`` + ``tick``. Returns the name of the API
    that took effect, for the record; raises if none did, because a still-running
    engine clock would make every timing judgement non-reproducible.
    """
    for name in ("pause", "pause_env", "stop_timer", "stop_time"):
        method = getattr(env, name, None)
        if callable(method):
            method()
            return name
    raise ClockTamper(
        "could not pause the ARE environment: none of pause/pause_env/stop_timer/stop_time "
        "is available, so the engine clock would run concurrently with the deterministic clock"
    )
