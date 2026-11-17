"""Per-task operand data for this AR9 temporal-deadline bundle (native redesign).

PURE DATA, no control flow and no seed->answer derivation. After the native-app
redesign the per-episode secret (the discovered values and whether the agent acted on
them correctly and before the cutoff) is derived in ``raven_ar9.realize.derive`` and
the private ``solution/truth.py``; the realized values are handed to the agent in the
E1 email. This module therefore carries only the universe-level operands that are not
derivable per episode.

Consumers (verified by grep over the engine package):
  * ``server.py::_expected_app_count`` reads ``UNIVERSE_APP_COUNT`` via ``getattr``
    (tolerant of absence) to assert the published surface covers every native app.
  * ``scenario.py`` imports ``UNIVERSE_APP_COUNT`` from ``realize`` (which defines its
    own copy), NOT from here; the two must stay equal (both 12).

The orphaned IncidentApp-era operands (CANDIDATES, SIGNALS, DEADLINE, TOKEN_ISSUE_TICK,
ORACLE_DAG, ADVANCE_PER_*, EFFECTIVE_EFFECT, EVIDENCE_ROUTING, ...) were dropped with the
deleted single-app mechanism: nothing in the engine
imported them.
"""

from __future__ import annotations

ARCHETYPE = "ar9_temporal_deadline"
SPEC_ID = "spec0"

# The 12 native universe apps imported from environment/universe_0.json (INTERFACES 0).
# scenario.init_and_populate_apps hard-fails unless exactly this many apps import with a
# non-empty get_state(); server._expected_app_count asserts the surface covers them.
UNIVERSE_APP_COUNT = 12

UNIVERSE_APP_NAMES: tuple[str, ...] = (
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

SKIPPED_UNIVERSE_APPS: tuple[str, ...] = ("SandboxLocalFileSystem",)
