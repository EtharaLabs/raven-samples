"""Per-task operand data for this AR9 transit-recovery bundle.

PURE DATA, no control flow and no seed->answer derivation. The per-episode values (the
discovered trip facts and whether the agent acted on them correctly and before the cutoff)
are derived in ``raven_ar9.realize.derive`` and graded by ``tests/score.py``. This module
carries only the universe-level operands that are not derivable per episode.

Consumers:
  * ``server.py::_expected_app_count`` reads ``UNIVERSE_APP_COUNT`` via ``getattr``.
  * ``scenario.py`` imports ``UNIVERSE_APP_COUNT`` from ``realize`` (its own copy); the two
    must stay equal (both 12).
"""

from __future__ import annotations

ARCHETYPE = "ar9_transit_recovery"
SPEC_ID = "spec0"

# The 12 native universe apps imported from environment/universe_0.json.
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
