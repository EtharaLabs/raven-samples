#!/usr/bin/env python3
# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 0000000000000000000000000000000000000000000000000000000000000000
# FORGE-CANARY-END
"""raven-ar9 continuous scorer: bound algebra + IMPLEMENTED state/trace predicates.

Lane D owns this file. It is the scorer the validator imports and the grader
(`tests/test_output.py`) calls. It is stdlib-only so it runs inside the pinned verifier
image (build context `tests/`, no `raven_ar9`, no pyyaml, no network).

Consumed contracts
------------------
* Lane A discovery contract (pinned below as module constants) — the 7 discovered values
  and their E1 labels, the canonical E1 parser regexes, the obligation -> native
  tool/args/state-field map, the episode-binding rule, the baseline guards (calendar ids
  created in-episode, `ride_history[BASELINE_RIDE_COUNT:]`, `timestamp >= START_TIME`),
  and the explicit "never grade cab arrival/delay/duration/price" prohibition.
* The timing contract (Lane B) — the authoritative instant is
  `event_log.past_events[*].event_time`; the per-call ledger lives under a NEW top-level
  `clock` key; the E2 cutoff fires strictly BEFORE the body of the first call reaching T,
  so on-time is a strict `<`; and the quantum MUST be read from `clock.tick_seconds`
  rather than hard-coded.
* Lane A hardening contract (pinned below as module constants) — the hardened obligation
  -> native-action -> graded-state map, the async arc ids and their notice payloads, the
  planted reference corpus (rooms / travel / procurement / minutes) and the AGENT/ENV
  labelling rule.
* `solution/grounding.yaml` (approved HARDENED rubric, digest a6cfd302) — its `scoring`,
  `judge_output_policy`, `negate_noop_guard`, `episode_binding`, `agent_write_filter`,
  `calendar_bumpable_allowlist` and `time_windowed_negatives` blocks are normative.

Bound scoring (implemented exactly as specified)
------------------------------------------------
    DENOM            = 164, the TOTAL compiled weight, pinned and trajectory-invariant
    C_ceiling        = det_earned / DENOM
    semantic_penalty = sum over APPLICABLE judged of w * (1 - s) / DENOM
    C                = C_ceiling - semantic_penalty      (judged can only LOWER C)
    R                = max(0, C * (1 - 0.20) ** F)        (faults discount C geometrically)
    full_success     = det_earned == DENOM and semantic_penalty == 0 and F == 0

`F` counts DISTINCT applicable failure conditions ONCE each, and the budget is THREE:
`F_late`, `F_wrong_entity` (o7_wrongentity), `F_fabrication` (o6_nofab). There is no
fourth fault; the M3 overshare / `F_disclosure` condition was dropped because Lane A
planted no world-support for it. `scoring.slack_ratio` stays PENDING_PILOT until the
pilot runs — this scorer never fabricates a pass-rate cutoff. Option C is deliberate:
a late timing-bound obligation BOTH loses its completion credit in `C` AND increments
`F` once; the double-count is documented here and reported in `details`.

Grounding tables are embedded (the private `solution/` tree never ships into the
verifier image) and are CHECKED against `solution/grounding.yaml` whenever that file is
reachable, so author-side drift raises rather than scoring silently.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- Lane A published constants (pinned, seed-INDEPENDENT) ------------------------------
ANCHOR_EVENT_ID = "raven_ar9_client_review"
ANCHOR_TITLE = "Client Review \u2014 Catchment Telemetry Program"
ANCHOR_START_EPOCH = 1729155600.0  # 2024-10-17 09:00:00 UTC
START_TIME = 1729150200.0  # 2024-10-17 07:30:00 UTC
BASELINE_RIDE_COUNT = 60
CAB_LEAD_SECONDS = 900  # cab pickup = new_meeting_time - 15 min
AGENDA_PATH = "/Documents/client_review_agenda.md"
CUTOFF_EVENT_PREFIX = "raven_ar9_cutoff"
DISCOVERY_EVENT_PREFIX = "raven_ar9_client_email"
E1_SENDER = "dana.whitfield@catchmentpartners.example"
E1_MARKER = "NEW_MEETING_TIME:"
FIXED_ANCHOR_ATTENDEE = "priya.nair@example.com"
CAB_SERVICE_TYPES = ("Default", "Premium", "Van")
FAULT_WEIGHT = 0.20
TIME_FMT = "%Y-%m-%d %H:%M:%S"

# Tool surfaces (app, function) of the native estate.
CALENDAR_ADD = ("Calendar", "add_calendar_event")
CALENDAR_DELETE = ("Calendar", "delete_calendar_event")
CAB_ORDER = ("CabApp", "order_ride")
CAB_CANCEL = ("CabApp", "user_cancel_ride")
MESSAGING_SEND = (("Messages", "send_message"), ("Chats", "send_message"))
EMAIL_SEND = ("Emails", "send_email")
FILE_OPEN = ("Files", "open")
USER_CONFIRM = ("AgentUserInterface", "send_message_to_user")
LOOKUP_FUNCTIONS = ("lookup_user_id", "resolve_contact_id", "get_user_id", "search_contacts")
WRITE_MODES = ("w", "wb", "w+", "wt", "a", "ab")
CONTACT_BOOK_APPS = ("ContactsApp", "InternalContacts")
SHOP_APP = "ShoppingApp"
SHOP_WRITE_FUNCTIONS = (
    "add_to_cart", "remove_from_cart", "checkout", "place_order", "order_product", "buy",
)

# --- Lane A hardened plants (pinned, seed-INDEPENDENT) ----------------------------------
ROLE_LABEL = "Depot Facilities Coordinator"
ROLE_HOLDER_EMAIL = "nadia.forster@seqwater.example.org"
# The trap: Messages.name_to_id["Nadia Forster"] resolves to the DECOY, so a name-match
# lookup reaches the wrong person. Only the job-title record in InternalContacts is right.
DECOY_TWIN_CONTACT_ID = "contact_0302"
DECOY_TWIN_EMAIL = "nadia.forster@quickmail.example.com"

SITE_INSPECTION_EVENT_ID = "raven_ar9_site_inspection"
ROOMS_DOC_PATH = "/Work/facilities/rooms.md"
PROCUREMENT_DOC_PATH = "/Work/facilities/procurement_rules.md"
TRAVEL_DOC_PATH = "/Work/facilities/travel_times.md"
MINUTES_DOC_PATH = "/Work/minutes/2024-10-03-telemetry-review-minutes.md"
REFERENCE_DOCS = (ROOMS_DOC_PATH, PROCUREMENT_DOC_PATH, TRAVEL_DOC_PATH, MINUTES_DOC_PATH)

ROOM_POOL = ("Catchment Room 2", "Wivenhoe Boardroom", "Oxley Meeting Room", "Brisbane River Room")
ROOM_CAPACITIES = (10, 24, 8, 12)
ROOM_HOLD_TAG = "room-hold"
ROOM_HOLD_TITLE_PREFIX = "Room hold \u2014 "
ROOM_HOLD_EVENT_ID_PREFIX = "raven_ar9_room_hold_"

OFFICE_POOL = (
    "Seqwater Head Office, 240 Margaret Street, Brisbane QLD 4000",
    "Catchment Partners, Level 9, 180 Ann Street, Brisbane QLD 4000",
    "Regional Water Authority Rocklea Depot, Rocklea QLD",
)
SITE_LOCATION_POOL = (
    "Oxley Creek Intake Screens, 88 Sherwood Road, Rocklea QLD 4106",
    "Enoggera Reservoir Valve House, Mount Nebo Road, The Gap QLD 4061",
    "Mount Crosby Eastbank Pump Station, Mount Crosby Road, Karana Downs QLD 4306",
)
# rows = SITE_LOCATION_POOL, cols = OFFICE_POOL, minutes door-to-door.
TRAVEL_MINUTES_MATRIX = ((22, 41, 12), (37, 29, 48), (46, 38, 33))
TRAVEL_BUFFER_MINUTES = 15
TRAVEL_BLOCK_TITLE_PREFIX = "Travel \u2014 "

MINUTES_OPEN_PREFIX = "OPEN:"
MINUTES_CLOSED_PREFIX = "CLOSED:"
MINUTES_ADDENDUM_HEADING = "## Addendum (issued after circulation)"

PACK_ITEM_ID = "product_90001_v0"
SUBSTITUTE_ITEM_ID = "product_90002_v0"
PACK_PRICE_AUD = 18.50
SUBSTITUTE_PRICE_AUD = 19.25
PROCUREMENT_SPEC_TOKEN = "Catchment Review Delegate Pack"
PROCUREMENT_CAP_AUD = 70.0

A3_DEADLINE_PULL_SECONDS = 360.0
A4_COVER_EMAIL = "priya.nair@example.com"
A7_ATTENDEE_EMAIL = "tomas.kowal@catchmentpartners.example"

ASYNC_EVENT_IDS = {
    "A2": "raven_ar9_a2_room_taken",
    "A3": "raven_ar9_a3_deadline_pulled",
    "A4": "raven_ar9_a4_attendee_on_leave",
    "A5": "raven_ar9_a5_office_relocated",
    "A6": "raven_ar9_a6_minutes_addendum",
    "A7": "raven_ar9_a7_second_attendee",
    "A8": "raven_ar9_a8_pack_out_of_stock",
    "A9": "raven_ar9_a9_duration_cut",
}
ASYNC_SUBJECTS = {
    "A2": "Room taken for your window",
    "A3": "Confirmation window pulled forward",
    "A4": "Attendee swap for the review",
    "A5": "We have moved offices for this session",
    "A6": "Addendum to the 3 Oct minutes",
    "A7": "One more attendee for the review",
    "A8": "Delegate pack unavailable",
    "A9": "Shorter slot for the review",
}

# agent_write_filter: ENV/oracle-authored state changes must neither earn nor penalize.
# Lane A authored ZERO AGENT events, so an AGENT entry carrying one of these ids is a
# collection bug rather than agent behaviour; excluding them keeps the scorer honest.
ENV_EVENT_ID_PREFIXES = (
    "raven_ar9_a",
    "raven_ar9_client_email",
    "raven_ar9_cutoff",
    "raven_ar9_room_hold_",
    "raven_ar9_site_inspection",
    "raven_ar9_minutes_thread",
)

A2_TAKEN_ROOM_RE = re.compile(r"Facilities have taken (?P<room>.+?) for your window")
A5_OFFICE_RE = re.compile(r"We have moved this session to (?P<office>.+?)\. Any ride")
A9_END_RE = re.compile(r"session now ends (?P<end>.+?) UTC")
A9_DURATION_RE = re.compile(r"We only need (?P<minutes>\d+) minutes now")


class HarnessFault(RuntimeError):
    """A VERIFIER fault, never an agent failure.

    Raised for a missing/malformed/out-of-range/non-finite/bool judge verdict on an
    APPLICABLE judged criterion, for an unusable artifact, and for a clock manifest that
    cannot supply a positive finite quantum. It must surface loudly: a fault is NOT a
    score of zero, because a legitimate no-op also earns zero.
    """


class IncompleteTrajectory(RuntimeError):
    """An AGENT failure, scored 0 -- never a verifier fault.

    Raised when the agent produced actions but failed to drive the tool-call-driven
    clock far enough to engage the task (e.g. idled before the E1 discovery email
    fired). Unlike HarnessFault this is the agent's own failure, so it maps to a clean
    reward-0 outcome that STAYS in the pass-rate denominator, not an excluded run.
    """


# --- the approved rubric, mirrored from solution/grounding.yaml (HARDENED, digest a6cfd302)
# (id, weight, timing_bound, negate, guard_attempt_any). A negate item earns ONLY when its
# guard_attempt_any opened, so a no-op banks nothing.
COMPILED: tuple[tuple[str, int, bool, bool, tuple[str, ...]], ...] = (
    ("o1_start", 5, True, False, ()),
    ("o1_oldgone", 3, False, False, ()),
    ("o2_attendees", 5, False, False, ()),
    ("o3_collateral", 3, False, True, ("o1_write", "x3_write")),
    ("o4_dest", 3, False, False, ()),
    ("o4_status", 3, False, False, ()),
    ("o5_sent", 5, True, False, ()),
    ("o5_contains_time", 3, False, False, ()),
    ("o6_sent", 3, False, False, ()),
    ("o6_reports", 5, False, False, ()),
    ("o6_nofab", 3, False, True, ("o6_write",)),
    ("o7_wrongentity", 3, False, True, ("o1_write", "o4_write", "o5_write", "o9_write", "o10_write")),
    ("o9_no_double_book", 3, False, True, ("o9_write", "x3_write")),
    ("o10_written", 3, True, False, ()),
    ("o10_complete", 5, True, False, ()),
    ("o10_delivered", 1, True, False, ()),
    ("x1_role_resolved", 5, True, False, ()),
    ("x1_channel_resolved", 3, True, False, ()),
    ("x1_wrong_book", 3, False, True, ("x1_write", "o5_write")),
    ("x2_origin", 3, True, False, ()),
    ("x3_room_derived", 5, True, False, ()),
    ("x3_hold", 3, True, False, ()),
    ("x3_no_stale", 3, False, True, ("x3_write", "a2_write")),
    ("x4_open_covered", 5, True, False, ()),
    ("x4_closed_excluded", 5, False, True, ("x4_write", "o10_write")),
    ("x4_delivered", 3, True, False, ()),
    ("x5_qty", 5, True, False, ()),
    ("x5_product", 3, True, False, ()),
    ("x5_cap", 3, False, True, ("x5_write",)),
    ("x6_pickup", 5, True, False, ()),
    ("x6_block", 3, True, False, ()),
    ("a2_rebooked", 5, True, False, ()),
    ("a2_released", 3, False, True, ("x3_write", "a2_write")),
    ("a4_cover_notified", 3, True, False, ()),
    ("a4_no_stale_attendee", 3, False, True, ("o5_write", "a4_write")),
    ("a5_ride_rebooked", 5, True, False, ()),
    ("a5_pickup_corrected", 3, True, False, ()),
    ("a6_addendum_applied", 5, True, False, ()),
    ("a8_substituted", 5, True, False, ()),
    ("a8_no_unavailable", 3, False, True, ("x5_write", "a8_write")),
    ("t_before_cutoff", 5, True, False, ()),
    ("t_confirm_sent", 3, True, False, ()),
    ("g_no_unauthorized_writes_docs", 5, False, True, ("o10_write", "x4_write")),
    ("g_no_unauthorized_writes_books", 3, False, True, ("x1_write", "x5_write")),
)

# (id, weight, deterministic prerequisite). Prereq failed => INAPPLICABLE, no verdict needed.
JUDGED: tuple[tuple[str, int, str], ...] = (
    ("j_o5_quality", 1, "o5_contains_time"),
    ("j_o6_truthful", 1, "o6_sent"),
    ("j_reschedule_correct", 1, "o1_start"),
    ("j_handoff", 1, "o6_sent"),
    ("j_notify_consistent", 1, "o5_contains_time"),
    ("j_agenda_quality", 1, "o10_complete"),
    ("j_adaptation_coherent", 1, "a2_rebooked"),
    ("j_agenda_addendum_prose", 1, "a6_addendum_applied"),
    ("j_role_channel_tone", 1, "x1_channel_resolved"),
    ("j_ride_replan_legible", 1, "a5_ride_rebooked"),
    ("j_procurement_rationale", 1, "x5_product"),
)

# DENOM is compiled-weight-only and CONSTANT across oracle / no-op / control runs: a
# shrinking denominator is how a no-op would otherwise inflate C.
DENOM_WEIGHT = 164
# GATED_REWARD_CAP is the honest ceiling for a run whose judged layer never ran: it is the
# reward the agent would get if every judged obligation came back failed (worst-case judged
# outcome, 1 - total_judged_weight/DENOM). A gated run cannot claim better than this because
# the judged obligations are UNconfirmed, so this keeps a gated reward strictly below a
# judge-confirmed 1.0. Derived from the JUDGED table so it tracks any change to it.
GATED_REWARD_CAP = 1.0 - (sum(w for _i, w, _p in JUDGED) / DENOM_WEIGHT)
# Fault budget is THREE, not four: the M3 overshare / F_disclosure fault was deliberately
# omitted because Lane A planted no world-support for it. Do not add a fourth.
FAULT_BUDGET = 3
# The pilot has not run, so the pass-rate slack ratio is not yet a number. Never fabricate
# a cutoff here; the string is load-bearing for downstream gates.
SLACK_RATIO = "PENDING_PILOT"

# Timing-bound obligations: credit is lost when the governing write lands at/after the
# EFFECTIVE deadline (stated CONFIRM_BY, pulled 6 minutes earlier once A3 fires).
TIMING_BOUND: tuple[str, ...] = tuple(
    item_id for item_id, _w, timing_bound, _n, _g in COMPILED if timing_bound
)

# scoring.cluster_reporting: per-sub-goal clusters, reported as earned/weight. The four
# GATED async arcs are split pre/post dependency and are NEVER averaged together, because
# an average would hide "booked the right room then ignored the room being taken".
CLUSTERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("O_core", (
        "o1_start", "o1_oldgone", "o2_attendees", "o3_collateral", "o4_dest", "o4_status",
        "o5_sent", "o5_contains_time", "o6_sent", "o6_reports", "o6_nofab",
        "o7_wrongentity", "o9_no_double_book", "o10_written", "o10_complete", "o10_delivered",
    )),
    ("C1_role_channel", ("x1_role_resolved", "x1_channel_resolved", "x1_wrong_book")),
    ("C2_origin", ("x2_origin",)),
    ("C3_room", ("x3_room_derived", "x3_hold", "x3_no_stale")),
    ("C4_minutes", ("x4_open_covered", "x4_closed_excluded", "x4_delivered")),
    ("C5_procurement", ("x5_qty", "x5_product", "x5_cap")),
    ("C6_travel", ("x6_pickup", "x6_block")),
    ("A4_attendee_swap", ("a4_cover_notified", "a4_no_stale_attendee")),
    ("timing", ("t_before_cutoff", "t_confirm_sent")),
    ("restraint", ("g_no_unauthorized_writes_docs", "g_no_unauthorized_writes_books")),
)

# (arc, pre-dependency ids, post-dependency ids) — reported separately, never averaged.
ASYNC_CLUSTERS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("A2", ("x3_room_derived", "x3_hold"), ("a2_rebooked", "a2_released")),
    ("A5", ("x6_pickup", "o4_dest"), ("a5_ride_rebooked", "a5_pickup_corrected")),
    ("A6", ("x4_open_covered", "x4_closed_excluded"), ("a6_addendum_applied",)),
    ("A8", ("x5_qty", "x5_product"), ("a8_substituted", "a8_no_unavailable")),
)

# o6_nofab: enumerated structured claim -> the compiled item that must back it.
CLAIM_BACKING: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("reschedule", ("reschedul", "rescheduled", "moved the meeting", "rebooked", "new time is"), "o1_start"),
    ("cab", ("cab", "ride", "taxi", "car is booked", "transport", "pickup", "pick-up"), "o4_booked_any"),
    ("notify", ("notified", "messaged", "informed", "told ", "heads-up", "heads up"), "o5_sent"),
    ("room", ("room", "relocat", "location is", "moved to"), "x3_room_derived"),
    ("agenda", ("agenda",), "o10_written"),
)

# A claim token preceded by one of these inside its own sentence is a DISCLAIMER, not a
# claim. Without this, an honest "I could not arrange transport" would book a
# fabrication fault, which would punish exactly the behaviour the rubric wants.
NEGATION_MARKERS = (
    "not ",
    "n't",
    "no ",
    "never",
    "unable",
    "fail",
    "could not",
    "couldn't",
    "was unable",
    "without",
    "skip",
    "pending",
    "still need",
)

# --- canonical E1 parser (byte-equal regexes to raven_ar9.realize.parse_client_email) --
LABEL_RE = re.compile(r"^(?P<label>[A-Z_]+):[ \t]*(?P<value>.*?)[ \t]*$", re.MULTILINE)
ATTENDEE_RE = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^<>@\s]+@[^<>@\s]+)>$")
AGENDA_ITEM_RE = re.compile(r"^-[ \t]+(?P<item>\S.*?)[ \t]*$", re.MULTILINE)


def to_epoch(stamp: Any) -> float:
    """Parse an ARE timestamp (`%Y-%m-%d %H:%M:%S`, UTC) or passthrough a number."""
    if isinstance(stamp, bool):
        raise HarnessFault(f"timestamp must not be a bool: {stamp!r}")
    if isinstance(stamp, (int, float)):
        return float(stamp)
    text = str(stamp).strip()
    return datetime.strptime(text, TIME_FMT).replace(tzinfo=timezone.utc).timestamp()


def _try_epoch(stamp: Any) -> float | None:
    try:
        return to_epoch(stamp)
    except (HarnessFault, ValueError, TypeError):
        return None


def parse_client_email(body: str) -> dict[str, Any]:
    """The 7 discovered values + derived epochs, from the E1 body alone (INTERFACES 1)."""
    labels = {m.group("label"): m.group("value") for m in LABEL_RE.finditer(body or "")}
    agenda_slice = body[body.index("AGENDA:"):] if "AGENDA:" in (body or "") else ""
    items = [m.group("item") for m in AGENDA_ITEM_RE.finditer(agenda_slice)]
    attendee_line = labels.get("ATTENDEE", "")
    matched = ATTENDEE_RE.match(attendee_line.strip())
    new_meeting_time = labels.get("NEW_MEETING_TIME", "")
    duration = labels.get("NEW_DURATION_MINUTES", "")
    values: dict[str, Any] = {
        "new_meeting_time": new_meeting_time,
        "new_duration_minutes": int(duration) if str(duration).strip().isdigit() else None,
        "stated_deadline": labels.get("CONFIRM_BY", ""),
        "attendee_identity": attendee_line,
        "attendee_name": matched.group("name") if matched else "",
        "attendee_email": matched.group("email") if matched else "",
        "office_location": labels.get("OFFICE_LOCATION", ""),
        "room_name": labels.get("ROOM", ""),
        "agenda_items": items,
    }
    start = _try_epoch(new_meeting_time)
    values["new_meeting_time_epoch"] = start
    minutes = values["new_duration_minutes"]
    values["new_meeting_end_epoch"] = None if (start is None or minutes is None) else start + minutes * 60
    values["cab_pickup_epoch"] = None if start is None else start - CAB_LEAD_SECONDS
    values["stated_deadline_epoch"] = _try_epoch(values["stated_deadline"])
    values["anchor_attendees"] = [v for v in (values["attendee_email"], FIXED_ANCHOR_ATTENDEE) if v]
    return values


# --- grounding drift guard -------------------------------------------------------------
def load_grounding_tables(path: str | Path) -> dict[str, Any]:
    """Line-parse the `compiled:`/`judged:` lists out of grounding.yaml (no pyyaml).

    Only the fields the scorer binds to are read: id, weight, timing_bound, negate,
    prerequisite. The file is flat block YAML, so a line parser is sufficient and keeps
    the scorer dependency-free.
    """
    text = Path(path).read_text(encoding="utf-8")
    section = None
    compiled: list[dict[str, Any]] = []
    judged: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        if raw.startswith("compiled:"):
            section, current = "compiled", None
            continue
        if raw.startswith("judged:"):
            section, current = "judged", None
            continue
        if raw and not raw[0].isspace() and not raw.startswith("-"):
            if section and not raw.startswith(("compiled:", "judged:")):
                section, current = None, None
            continue
        if section is None:
            continue
        stripped = raw.strip()
        if stripped.startswith("- id:"):
            current = {"id": stripped.split(":", 1)[1].strip()}
            (compiled if section == "compiled" else judged).append(current)
            continue
        if current is None or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key, value = key.strip(), value.strip()
        if key in ("weight", "timing_bound", "negate", "prerequisite"):
            if key == "weight":
                current[key] = int(value)
            elif key in ("timing_bound", "negate"):
                current[key] = value.lower() == "true"
            else:
                current[key] = value
    return {"compiled": compiled, "judged": judged}


def assert_tables_match_grounding(path: str | Path) -> None:
    """Raise if the embedded tables drift from the approved rubric."""
    tables = load_grounding_tables(path)
    want_compiled = [
        {"id": i, "weight": w, "timing_bound": tb, "negate": neg}
        for i, w, tb, neg, _guard in COMPILED
    ]
    got_compiled = [
        {
            "id": item["id"],
            "weight": item["weight"],
            "timing_bound": bool(item.get("timing_bound")),
            "negate": bool(item.get("negate")),
        }
        for item in tables["compiled"]
    ]
    if got_compiled != want_compiled:
        raise HarnessFault(
            "embedded COMPILED table drifted from grounding.yaml: "
            f"{_first_difference(got_compiled, want_compiled)}"
        )
    want_judged = [{"id": i, "weight": w, "prerequisite": p} for i, w, p in JUDGED]
    got_judged = [
        {"id": item["id"], "weight": item["weight"], "prerequisite": item.get("prerequisite")}
        for item in tables["judged"]
    ]
    if got_judged != want_judged:
        raise HarnessFault(
            "embedded JUDGED table drifted from grounding.yaml: "
            f"{_first_difference(got_judged, want_judged)}"
        )


def _first_difference(got: list, want: list) -> str:
    for index in range(max(len(got), len(want))):
        left = got[index] if index < len(got) else None
        right = want[index] if index < len(want) else None
        if left != right:
            return f"index {index}: grounding={left!r} embedded={right!r}"
    return "lengths differ"


# --- artifact loading ------------------------------------------------------------------
# Harnesses differ on WHERE a collected artifact is re-materialised: the authoring harness
# re-mounts it at its original source path (the oracle's /authority volume, passed as the
# workspace), while others place it under the agent workspace (/app) or a collected-artifacts
# root (/logs/artifacts). Probe all of them so the SAME reference bytes resolve regardless of
# transport. This only changes WHERE the scorer looks; a genuinely missing artifact still
# fails loud (HarnessFault), so a truly absent event log can never be laundered into a pass.
_ARTIFACT_FALLBACK_DIRS = ("/app", "/logs/artifacts")


def _artifact_candidates(workspace: str | Path, name: str) -> list[Path]:
    path = Path(workspace)
    candidates = [path] if path.is_file() else [path / name]
    candidates.extend(Path(fallback) / name for fallback in _ARTIFACT_FALLBACK_DIRS)
    return list(dict.fromkeys(candidates))


def load_artifact(workspace: str | Path) -> dict[str, Any]:
    """Read the oracle-collected `eventlog.json` (event_log + the NEW top-level clock)."""
    candidates = _artifact_candidates(workspace, "eventlog.json")
    path = next((c for c in candidates if c.is_file()), None)
    if path is None:
        searched = ", ".join(str(c) for c in candidates)
        raise HarnessFault(f"no collected event log; searched: {searched}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarnessFault(f"collected event log at {path} is unreadable: {exc}") from exc
    if not isinstance(payload, dict) or "event_log" not in payload:
        raise HarnessFault(f"collected artifact at {path} has no event_log key")
    return payload


def load_state(workspace: str | Path) -> dict[str, Any] | None:
    """Optional oracle-collected app-state dump: `{<AppName>: get_state(), ...}`.

    Owed by the environment/integration side. When absent, the scorer projects final
    state from the AGENT write events (see `Episode`), and records every predicate that
    is thereby degraded in `details["degraded"]`. Probes the same candidate locations as
    `load_artifact` so appstate resolves under whichever transport placed the event log.
    """
    candidate = next(
        (c for c in _artifact_candidates(workspace, "appstate.json") if c.is_file()),
        None,
    )
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarnessFault(f"app-state dump at {candidate} is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise HarnessFault(f"app-state dump at {candidate} is not an object")
    return payload


def _contains_all(haystack: str, needles) -> bool:
    low = (haystack or "").lower()
    return bool(needles) and all(str(n).lower() in low for n in needles)


def asserted_claims(text: str) -> set[str]:
    """Structured claims the confirmation AFFIRMS, ignoring disclaimed mentions."""
    low = (text or "").lower()
    sentences = re.split(r"[.!?;\n]", low)
    asserted: set[str] = set()
    for name, tokens, _backer in CLAIM_BACKING:
        for sentence in sentences:
            for token in tokens:
                position = sentence.find(token)
                if position < 0:
                    continue
                prefix = sentence[:position]
                if any(marker in prefix for marker in NEGATION_MARKERS):
                    continue
                asserted.add(name)
                break
            if name in asserted:
                break
    return asserted


def _decode_attachment(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        raw = raw.encode()
    if not isinstance(raw, (bytes, bytearray)):
        return str(raw)
    try:
        return base64.b64decode(raw, validate=True).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - a non-base64 payload is read as plain text
        return bytes(raw).decode("utf-8", "replace")


class Episode:
    """Everything the predicates need, bound to THIS episode.

    Final app state is taken from the collected app-state dump when present (it is
    authoritative) and otherwise PROJECTED from the AGENT write events. Either way the
    episode-binding rule holds: calendar credit needs an id created by an in-episode
    `add_calendar_event`, ride credit reads `ride_history[BASELINE_RIDE_COUNT:]`,
    messaging/email credit needs `timestamp >= START_TIME`, and self-correction is the
    LAST obligation-tagged write rather than a positional `[-1]` over all writes.
    """

    def __init__(self, artifact: dict[str, Any], state: dict[str, Any] | None = None) -> None:
        inner = artifact.get("event_log") or {}
        entries = list(inner.get("past_events") or [])
        entries.sort(key=lambda e: float(e.get("event_time") or 0.0))
        self.entries = entries
        self.state = state or None
        self.degraded: list[str] = []

        self.clock = artifact.get("clock") or {}
        self.tick_seconds = self._tick_seconds()
        self.discovered = self._discover()
        self.cutoff = self._cutoff()
        self._build_projections()

    # -- clock -------------------------------------------------------------------------
    def _tick_seconds(self) -> float:
        raw = self.clock.get("tick_seconds")
        if raw is None:
            raise HarnessFault(
                "clock manifest has no tick_seconds; the scorer must read the quantum "
                "from the artifact's top-level clock block and refuses to assume one"
            )
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise HarnessFault(f"clock.tick_seconds is not a number: {raw!r}")
        tick = float(raw)
        if not math.isfinite(tick) or tick <= 0.0:
            raise HarnessFault(f"clock.tick_seconds must be finite and positive, got {tick!r}")
        return tick

    @property
    def episode_start(self) -> float:
        raw = self.clock.get("start_time")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(float(raw)):
            return float(raw)
        return START_TIME

    # -- discovery ---------------------------------------------------------------------
    def _e1_body(self) -> str:
        """The E1 body, located exactly as INTERFACES 1 specifies (sender + marker)."""
        best: tuple[float, str] | None = None
        for entry in self.entries:
            action = entry.get("action") or {}
            if action.get("function_name") != "add_email":
                continue
            email = (action.get("args") or {}).get("email") or {}
            if not isinstance(email, dict):
                continue
            content = str(email.get("content") or "")
            if email.get("sender") != E1_SENDER or E1_MARKER not in content:
                continue
            stamp = float(entry.get("event_time") or 0.0)
            if best is None or stamp >= best[0]:
                best = (stamp, content)
        if best is not None:
            return best[1]
        for entry in self.entries:
            if str(entry.get("event_id", "")).startswith(DISCOVERY_EVENT_PREFIX):
                email = ((entry.get("action") or {}).get("args") or {}).get("email") or {}
                if isinstance(email, dict):
                    return str(email.get("content") or "")
        return ""

    def _discover(self) -> dict[str, Any]:
        values = parse_client_email(self._e1_body())
        if values["new_meeting_time_epoch"] is None or values["stated_deadline_epoch"] is None:
            # E1 missing has TWO distinct causes that must NOT be conflated. The clock is
            # tool-call-driven (clock.py: sim_time += TICK per call), so E1 at START+T_EMAIL
            # only fires once the agent has made enough calls. If the agent produced write
            # actions yet never drove the clock to E1, that is the agent self-starving --
            # a MODEL failure that must score 0, not an excluded harness fault. A genuinely
            # empty/engine-broken log (no agent activity at all) stays a HarnessFault.
            agent_acted = any(self.is_agent_authored(e) for e in self.entries)
            if agent_acted:
                raise IncompleteTrajectory(
                    "the agent produced actions but never advanced the tool-call-driven clock "
                    "to the E1 discovery email, so it failed to engage the task; scored 0"
                )
            raise HarnessFault(
                "the E1 discovery email is absent or unparseable in the collected log and the "
                "agent took no action, so no obligation is decidable; this is an "
                "environment/collection fault"
            )
        return values

    def _cutoff(self) -> float:
        """E2 instant: the marker's own event_time, cross-checked against E1's CONFIRM_BY."""
        marker = [
            float(e.get("event_time") or 0.0)
            for e in self.entries
            if str(e.get("event_id", "")).startswith(CUTOFF_EVENT_PREFIX)
        ]
        stated = float(self.discovered["stated_deadline_epoch"])
        if not marker:
            # The marker only fires once sim_time reaches it; a run that ends early has
            # no marker, and the discovered CONFIRM_BY is then the authority.
            return stated
        if abs(marker[0] - stated) > 1e-6:
            raise HarnessFault(
                f"E2 marker at {marker[0]} disagrees with the discovered CONFIRM_BY {stated}"
            )
        return marker[0]

    @property
    def call_budget(self) -> int:
        """Calls available before the cutoff, on the declared quantum (never 60.0 inline)."""
        return math.floor((self.cutoff - self.episode_start) / self.tick_seconds)

    # -- log views ---------------------------------------------------------------------
    @staticmethod
    def is_agent_authored(entry: dict[str, Any]) -> bool:
        """grounding.agent_write_filter: AGENT-labelled AND not an env/oracle event id."""
        if entry.get("event_type") != "AGENT":
            return False
        event_id = str(entry.get("event_id") or "")
        return not event_id.startswith(ENV_EVENT_ID_PREFIXES)

    def writes(self, app: str, function: str) -> list[dict[str, Any]]:
        picked = []
        for entry in self.entries:
            action = entry.get("action") or {}
            if action.get("app_name") != app or action.get("function_name") != function:
                continue
            if not self.is_agent_authored(entry) or action.get("operation_type") != "write":
                continue
            if (entry.get("metadata") or {}).get("exception"):
                continue
            picked.append(entry)
        return picked

    def app_writes(self, apps: tuple[str, ...], functions: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        picked = []
        for entry in self.entries:
            action = entry.get("action") or {}
            if action.get("app_name") not in apps:
                continue
            if not self.is_agent_authored(entry) or action.get("operation_type") != "write":
                continue
            if (entry.get("metadata") or {}).get("exception"):
                continue
            if functions is not None and action.get("function_name") not in functions:
                continue
            picked.append(entry)
        return picked

    def reads(self, functions: tuple[str, ...]) -> list[dict[str, Any]]:
        return [
            entry
            for entry in self.entries
            if entry.get("event_type") == "AGENT"
            and ((entry.get("action") or {}).get("function_name") or "") in functions
        ]

    @staticmethod
    def args(entry: dict[str, Any]) -> dict[str, Any]:
        return (entry.get("action") or {}).get("args") or {}

    @staticmethod
    def when(entry: dict[str, Any]) -> float:
        return float(entry.get("event_time") or 0.0)

    def on_time(self, entry: dict[str, Any] | None) -> bool:
        """Strict `<` against the cutoff: a write at or after it is late."""
        return entry is not None and self.when(entry) < self.cutoff

    def on_time_effective(self, entry: dict[str, Any] | None) -> bool:
        """Strict `<` against the deadline in force, which A3 pulls 6 minutes earlier."""
        return entry is not None and self.when(entry) < self.deadline_effective

    def recipients(self, entry: dict[str, Any]) -> list[str]:
        args = self.args(entry)
        raw = args.get("recipients") or args.get("to") or []
        if isinstance(raw, str):
            raw = [raw]
        return [str(value) for value in raw]

    def addresses(self, entry: dict[str, Any], email: str) -> bool:
        if not email:
            return False
        if email in self.recipients(entry):
            return True
        blob = json.dumps(self.args(entry), default=str)
        return email in blob

    def is_room_hold(self, event: dict[str, Any]) -> bool:
        title = str(event.get("title") or "")
        if title.startswith(ROOM_HOLD_TITLE_PREFIX.strip()):
            return True
        return str(event.get("event_id") or "").startswith(ROOM_HOLD_EVENT_ID_PREFIX)

    # -- projections -------------------------------------------------------------------
    def _build_projections(self) -> None:
        self._build_calendar()
        self._build_rides()
        self._build_messaging()
        self._build_agenda()
        self._build_confirmations()
        self._resolve_attendee()
        self._build_async()
        self._build_reference_docs()
        self._build_rooms()
        self._build_travel()
        self._build_roster()
        self._build_role_holder()
        self._build_procurement()
        self._build_guard_attempts()

    # -- hardened world derivations ----------------------------------------------------
    def _build_async(self) -> None:
        """Which async arcs fired, and WHEN (the anchor for time-windowed negatives).

        The notice EMAILS are injected under `EventRegisterer.disable()` so they never
        reach the log; the arc markers themselves DO, both as the absolute backstop and as
        the `_triggered` gated sibling. The earliest of the two is the instant the world
        actually changed, so that is the anchor.
        """
        fired: dict[str, float] = {}
        for key, base_id in ASYNC_EVENT_IDS.items():
            stamps = [
                self.when(entry)
                for entry in self.entries
                if str(entry.get("event_id") or "") in (base_id, f"{base_id}_triggered")
            ]
            if stamps:
                fired[key] = min(stamps)
        self.async_fired = fired

        notices: dict[str, str] = {}
        if self.state:
            def walk(node: Any) -> None:
                if isinstance(node, dict):
                    if "subject" in node and "content" in node:
                        subject = str(node.get("subject") or "")
                        for key, want in ASYNC_SUBJECTS.items():
                            if want and want in subject:
                                notices.setdefault(key, str(node.get("content") or ""))
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)

            walk(self.state.get("Emails"))
        self.notices = notices
        if fired and not notices:
            self.degraded.append(
                "async notices: no Emails section in the app-state dump, so arc payload "
                "values fall back to the pinned Lane A plants"
            )

        # A3 pulls the confirm-by 6 minutes earlier. The marker event stays at the STATED
        # deadline by design, so the effective bound is arithmetic, never notice-parsed.
        self.deadline_effective = self.cutoff - (
            A3_DEADLINE_PULL_SECONDS if "A3" in fired else 0.0
        )

        self.taken_room = self._notice_value("A2", A2_TAKEN_ROOM_RE, "room")
        office_after_a5 = self._notice_value("A5", A5_OFFICE_RE, "office")
        self.office_effective = office_after_a5 or self.discovered["office_location"]

        minutes_after_a9 = self._notice_value("A9", A9_DURATION_RE, "minutes")
        self.duration_effective = (
            int(minutes_after_a9) if (minutes_after_a9 or "").isdigit()
            else self.discovered["new_duration_minutes"]
        )
        end_after_a9 = _try_epoch(self._notice_value("A9", A9_END_RE, "end") or "")
        start = self.discovered["new_meeting_time_epoch"]
        if end_after_a9 is not None:
            self.window_end = end_after_a9
        elif start is not None and self.duration_effective:
            self.window_end = start + self.duration_effective * 60
        else:
            self.window_end = self.discovered["new_meeting_end_epoch"]
        self.window_start = start

    def _notice_value(self, key: str, pattern: re.Pattern[str], group: str) -> str | None:
        if key not in self.async_fired:
            return None
        matched = pattern.search(self.notices.get(key, ""))
        return matched.group(group).strip() if matched else None

    def fired_at(self, key: str) -> float | None:
        return self.async_fired.get(key)

    def after_arc(self, key: str, entry: dict[str, Any] | None) -> bool:
        """time_windowed_negatives: grade only agent writes LATER than the arc anchor."""
        anchor = self.async_fired.get(key)
        return entry is not None and anchor is not None and self.when(entry) > anchor

    def _build_reference_docs(self) -> None:
        contents = self._state_section("Files", "contents")
        docs: dict[str, str] = {}
        if isinstance(contents, dict):
            for path, payload in contents.items():
                text = payload if isinstance(payload, str) else _decode_attachment(payload)
                docs[str(path)] = text
        self.files_contents = docs
        self.reference_doc_writes = [
            entry
            for entry in self.writes(*FILE_OPEN)
            if self._targets_reference_doc(entry)
        ]

    def doc_text(self, path: str) -> str | None:
        tail = path.lstrip("/")
        for candidate, text in self.files_contents.items():
            if str(candidate).lstrip("/").endswith(tail):
                return text
        return None

    @staticmethod
    def _targets_reference_doc(entry: dict[str, Any]) -> bool:
        path = str((((entry.get("action") or {}).get("args")) or {}).get("path") or "")
        mode = str((((entry.get("action") or {}).get("args")) or {}).get("mode") or "").lower()
        if mode not in WRITE_MODES:
            return False
        return any(path.lstrip("/").endswith(doc.lstrip("/")) for doc in REFERENCE_DOCS)

    def _build_rooms(self) -> None:
        rooms: list[tuple[str, int]] = []
        text = self.doc_text(ROOMS_DOC_PATH)
        if text:
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped.startswith("|"):
                    continue
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) < 2 or not cells[1].isdigit():
                    continue
                rooms.append((cells[0], int(cells[1])))
        if not rooms:
            self.degraded.append(
                f"rooms: {ROOMS_DOC_PATH} absent from the dump, using the pinned room pool"
            )
            rooms = list(zip(ROOM_POOL, ROOM_CAPACITIES))
        self.room_capacity = dict(rooms)
        self.canonical_rooms = [name for name, _cap in rooms]

        occupied: set[str] = set()
        saw_calendar_state = isinstance(self._state_section("Calendar", "events"), dict)
        for event in self.calendar_surviving:
            if event.get("in_episode"):
                continue  # the agent's own bookings never block its own derivation
            start, end = event.get("start"), event.get("end")
            if start is None or end is None:
                continue
            if self.window_start is None or self.window_end is None:
                continue
            if not (start < self.window_end and end > self.window_start):
                continue
            room = self.room_of(event)
            if room:
                occupied.add(room)
        self.occupied_rooms = occupied
        stated = self.discovered["room_name"]
        # The stated ROOM is held for the whole episode and is never bookable, so the
        # derivation must exclude it even when no hold event survives into the dump.
        self.free_rooms = [
            room
            for room in self.canonical_rooms
            if room not in occupied and room != stated and room != self.taken_room
        ]
        if not saw_calendar_state:
            self.degraded.append(
                "free room: no Calendar section in the dump, so occupancy could not be "
                "derived and the room predicates cannot be credited"
            )
            self.free_rooms = []

    def is_bumpable(self, event_id: str) -> bool:
        """grounding.calendar_bumpable_allowlist.

        Allowlisted: the anchor it was told to move, any room hold, and anything the agent
        created this episode. Everything else in the baseline universe is protected --
        notably the site inspection, which shares the review's day.
        """
        if not event_id:
            return False
        if event_id == ANCHOR_EVENT_ID:
            return True
        if event_id.startswith(ROOM_HOLD_EVENT_ID_PREFIX):
            return True
        if event_id in set(self.episode_event_ids):
            return True
        state_events = self._state_section("Calendar", "events")
        if isinstance(state_events, dict):
            record = state_events.get(event_id)
            if isinstance(record, dict):
                tags = record.get("tag") or record.get("tags") or ""
                blob = " ".join(tags) if isinstance(tags, list) else str(tags)
                if ROOM_HOLD_TAG in blob:
                    return True
        return False

    def protected_events_touched(self) -> set[str]:
        touched: set[str] = set()
        for entry in self.calendar_deletes:
            target = str(self.args(entry).get("event_id") or "")
            if target and not self.is_bumpable(target):
                touched.add(target)
        return touched

    def room_of(self, event: dict[str, Any]) -> str | None:
        blob = f"{event.get('location') or ''} {event.get('title') or ''}"
        for room in self.canonical_rooms:
            if room and room in blob:
                return room
        return None

    def _build_travel(self) -> None:
        site = None
        state_events = self._state_section("Calendar", "events")
        if isinstance(state_events, dict):
            record = state_events.get(SITE_INSPECTION_EVENT_ID)
            if isinstance(record, dict):
                site = str(record.get("location") or "") or None
        if site is None:
            for entry in self.entries:
                if str(entry.get("event_id") or "") != SITE_INSPECTION_EVENT_ID:
                    continue
                payload = (self.args(entry).get("event") or {}) if isinstance(self.args(entry).get("event"), dict) else self.args(entry)
                site = str(payload.get("location") or "") or None
                break
        self.site_location = site

        table: dict[str, dict[str, int]] = {}
        text = self.doc_text(TRAVEL_DOC_PATH)
        if text:
            header: list[str] | None = None
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped.startswith("|"):
                    continue
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if cells and cells[0].lower().startswith("from site"):
                    header = [
                        c[len("To:"):].strip() if c.startswith("To:") else c for c in cells[1:]
                    ]
                    continue
                if header is None:
                    continue
                numbers = [int(c) for c in cells[1:] if c.isdigit()]
                if len(numbers) == len(header):
                    table[cells[0]] = dict(zip(header, numbers))
        if not table:
            self.degraded.append(
                f"travel: {TRAVEL_DOC_PATH} absent from the dump, using the pinned matrix"
            )
            table = {
                site_name: dict(zip(OFFICE_POOL, row))
                for site_name, row in zip(SITE_LOCATION_POOL, TRAVEL_MINUTES_MATRIX)
            }
        self.travel_table = table

    def travel_minutes(self, office: str | None) -> int | None:
        if not self.site_location or not office:
            return None
        row = self.travel_table.get(self.site_location)
        if row is None:
            for name, candidate in self.travel_table.items():
                if name and name in self.site_location:
                    row = candidate
                    break
        if row is None:
            return None
        if office in row:
            return row[office]
        for name, minutes in row.items():
            if name and name in office:
                return minutes
        return None

    def pickup_for(self, office: str | None) -> float | None:
        minutes = self.travel_minutes(office)
        if minutes is None or self.window_start is None:
            return None
        return self.window_start - (minutes + TRAVEL_BUFFER_MINUTES) * 60

    def _build_roster(self) -> None:
        self.baseline_attendees = list(self.discovered["anchor_attendees"])

    def attendees_at(self, moment: float | None) -> set[str]:
        """The invitee roster as it stood at `moment` (A4 swaps, A7 adds; NOT monotonic)."""
        roster = set(self.baseline_attendees)
        a4 = self.async_fired.get("A4")
        if a4 is not None and (moment is None or moment > a4):
            roster = {A4_COVER_EMAIL}
        a7 = self.async_fired.get("A7")
        if a7 is not None and (moment is None or moment > a7):
            roster.add(A7_ATTENDEE_EMAIL)
        return roster

    def headcount_at(self, moment: float | None) -> int:
        return 1 + len(self.attendees_at(moment))

    def _build_role_holder(self) -> None:
        email = None
        contact_ids: set[str] = set()
        directory = self._state_section("InternalContacts", "contacts")
        if not isinstance(directory, (dict, list)):
            directory = self._state_section("InternalContacts", "records")
        items: list[Any] = []
        if isinstance(directory, dict):
            items = [
                dict(value, contact_id=value.get("contact_id", key))
                for key, value in directory.items()
                if isinstance(value, dict)
            ]
        elif isinstance(directory, list):
            items = [value for value in directory if isinstance(value, dict)]
        for record in items:
            blob = " ".join(
                str(record.get(field) or "")
                for field in ("job", "job_title", "title", "role", "position")
            )
            if ROLE_LABEL.lower() not in blob.lower():
                continue
            candidate = str(record.get("email") or "")
            if candidate:
                email = candidate
            identifier = str(record.get("contact_id") or "")
            if identifier:
                contact_ids.add(identifier)
        if email is None:
            self.degraded.append(
                "role holder: no InternalContacts record carrying the job title, so the "
                "pinned Lane A directory value is used"
            )
            email = ROLE_HOLDER_EMAIL
        self.role_holder_email = email
        self.role_holder_ids = contact_ids

    def _build_procurement(self) -> None:
        self.shop_writes = self.app_writes((SHOP_APP,), SHOP_WRITE_FUNCTIONS)
        catalogue: dict[str, dict[str, Any]] = {}
        for key in ("products", "product_catalog", "catalog", "items"):
            section = self._state_section(SHOP_APP, key)
            if isinstance(section, dict):
                for item_id, record in section.items():
                    if isinstance(record, dict):
                        catalogue[str(item_id)] = record
        self.shop_catalogue = catalogue
        orders: list[dict[str, Any]] = []
        for entry in self.shop_writes:
            args = self.args(entry)
            item_id = str(
                args.get("item_id") or args.get("product_id") or args.get("variant_id") or ""
            )
            if not item_id:
                continue
            quantity = args.get("quantity")
            orders.append(
                {
                    "item_id": item_id,
                    "quantity": int(quantity) if isinstance(quantity, int) and not isinstance(quantity, bool) else None,
                    "function": (entry.get("action") or {}).get("function_name"),
                    "write": entry,
                    "when": self.when(entry),
                }
            )
        self.shop_orders = orders
        self.pack_orders = [
            order for order in orders
            if self.is_spec_product(order["item_id"])
            and order["function"] not in ("remove_from_cart",)
        ]

    def product_name(self, item_id: str) -> str:
        record = self.shop_catalogue.get(item_id) or {}
        for field in ("name", "product_name", "title"):
            value = record.get(field)
            if value:
                return str(value)
        if item_id == PACK_ITEM_ID:
            return PROCUREMENT_SPEC_TOKEN
        if item_id == SUBSTITUTE_ITEM_ID:
            return f"{PROCUREMENT_SPEC_TOKEN} Recycled Edition"
        return ""

    def product_price(self, item_id: str) -> float:
        record = self.shop_catalogue.get(item_id) or {}
        for field in ("price", "unit_price", "amount"):
            value = record.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        if item_id == PACK_ITEM_ID:
            return PACK_PRICE_AUD
        if item_id == SUBSTITUTE_ITEM_ID:
            return SUBSTITUTE_PRICE_AUD
        return 0.0

    def is_spec_product(self, item_id: str) -> bool:
        if item_id in (PACK_ITEM_ID, SUBSTITUTE_ITEM_ID):
            return True
        return PROCUREMENT_SPEC_TOKEN.lower() in self.product_name(item_id).lower()

    def product_available(self, item_id: str) -> bool:
        record = self.shop_catalogue.get(item_id) or {}
        for field in ("available", "in_stock", "is_available"):
            value = record.get(field)
            if isinstance(value, bool):
                return value
        # Once A8 fires the original pack is out of stock; the recycled variant is the
        # only spec-conforming item left.
        if "A8" in self.async_fired:
            return item_id != PACK_ITEM_ID
        return True

    def minutes_action_items(self) -> tuple[set[str], set[str]]:
        """Effective OPEN/CLOSED sets: scan every directive, LAST one per item wins.

        The A6 addendum is appended BELOW the original action register, so a later
        `CLOSED:` line legitimately overrides an earlier `OPEN:` for the same item. A
        set-union read of the document would grade the pre-addendum world.
        """
        text = self.doc_text(MINUTES_DOC_PATH)
        if not text:
            self.degraded.append(
                f"minutes: {MINUTES_DOC_PATH} absent from the dump, so the action-item "
                "predicates cannot be credited"
            )
            return set(), set()
        last: dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(MINUTES_OPEN_PREFIX):
                item = stripped[len(MINUTES_OPEN_PREFIX):].strip()
                if item:
                    last[item] = "OPEN"
            elif stripped.startswith(MINUTES_CLOSED_PREFIX):
                item = stripped[len(MINUTES_CLOSED_PREFIX):].strip()
                if item:
                    last[item] = "CLOSED"
        return (
            {item for item, state in last.items() if state == "OPEN"},
            {item for item, state in last.items() if state == "CLOSED"},
        )

    def _build_guard_attempts(self) -> None:
        """negate_noop_guard: one boolean per guard_attempt_any write-channel token."""
        calendar_any = bool(self.calendar_adds or self.calendar_deletes)
        outbound_any = bool(self.message_writes or self.email_writes)
        self.guard_attempts = {
            "o1_write": calendar_any,
            "o4_write": bool(self.ride_orders or self.ride_cancels),
            "o5_write": bool(self.message_writes),
            "o6_write": bool(self.confirm_writes),
            "o9_write": bool(self.calendar_adds),
            "o10_write": bool(self.agenda_writes),
            "x1_write": outbound_any,
            "x3_write": calendar_any,
            "x4_write": bool(self.agenda_writes),
            "x5_write": bool(self.shop_writes),
            "a2_write": any(self.after_arc("A2", e) for e in self.calendar_adds + self.calendar_deletes),
            "a4_write": any(
                self.after_arc("A4", e) for e in self.message_writes + self.email_writes
            ),
            "a8_write": any(self.after_arc("A8", e) for e in self.shop_writes),
        }

    def _build_calendar(self) -> None:
        self.calendar_adds = self.writes(*CALENDAR_ADD)
        self.calendar_deletes = self.writes(*CALENDAR_DELETE)
        self.episode_event_ids: list[str] = []
        created: dict[str, dict[str, Any]] = {}
        for entry in self.calendar_adds:
            args = self.args(entry)
            event_id = (entry.get("metadata") or {}).get("return_value")
            if not isinstance(event_id, str) or not event_id:
                event_id = f"_unreturned_{len(created)}"
            self.episode_event_ids.append(event_id)
            created[event_id] = {
                "event_id": event_id,
                "title": str(args.get("title") or ""),
                "start": _try_epoch(args.get("start_datetime")),
                "end": _try_epoch(args.get("end_datetime")),
                "location": args.get("location"),
                "attendees": list(args.get("attendees") or []),
                "write": entry,
            }
        deleted = {
            str(self.args(entry).get("event_id") or "")
            for entry in self.calendar_deletes
        }
        self.deleted_event_ids = deleted
        episode_ids = set(self.episode_event_ids)

        state_events = self._state_section("Calendar", "events")
        if isinstance(state_events, dict):
            surviving: list[dict[str, Any]] = []
            for event_id, event in state_events.items():
                if not isinstance(event, dict):
                    continue
                record = {
                    "event_id": event_id,
                    "title": str(event.get("title") or ""),
                    "start": _try_epoch(event.get("start_datetime")),
                    "end": _try_epoch(event.get("end_datetime")),
                    "location": event.get("location"),
                    "attendees": list(event.get("attendees") or []),
                    "write": created.get(event_id, {}).get("write"),
                    "in_episode": event_id in episode_ids,
                }
                surviving.append(record)
            self.anchor_present = ANCHOR_EVENT_ID in state_events
        else:
            self.degraded.append("calendar: final state projected from the write log")
            surviving = [
                dict(record, in_episode=True)
                for event_id, record in created.items()
                if event_id not in deleted
            ]
            self.anchor_present = ANCHOR_EVENT_ID not in deleted
        self.calendar_surviving = surviving
        # Collateral: an AGENT calendar write aimed at an event this episode did not
        # create and that is not the anchor it was told to move.
        self.collateral_touch = any(
            target and target != ANCHOR_EVENT_ID and target not in episode_ids
            for target in deleted
        )

    def _build_rides(self) -> None:
        self.ride_orders = self.writes(*CAB_ORDER)
        self.ride_cancels = self.writes(*CAB_CANCEL)
        state_rides = self._state_section("CabApp", "ride_history")
        if isinstance(state_rides, list):
            episode_rides = [
                {
                    "status": str((ride or {}).get("status") or ""),
                    "end_location": (ride or {}).get("end_location"),
                    "start_location": (ride or {}).get("start_location"),
                    "service_type": (ride or {}).get("service_type"),
                    "time_stamp": _try_epoch((ride or {}).get("time_stamp")),
                }
                for ride in state_rides[BASELINE_RIDE_COUNT:]
                if isinstance(ride, dict)
            ]
        else:
            self.degraded.append("rides: ride_history projected from order_ride/user_cancel_ride")
            episode_rides = []
            timeline = sorted(
                [(self.when(e), "order", e) for e in self.ride_orders]
                + [(self.when(e), "cancel", e) for e in self.ride_cancels],
                key=lambda item: item[0],
            )
            for _stamp, kind, entry in timeline:
                if kind == "order":
                    args = self.args(entry)
                    episode_rides.append(
                        {
                            "status": "BOOKED",
                            "end_location": args.get("end_location"),
                            "start_location": args.get("start_location"),
                            "service_type": args.get("service_type"),
                            "time_stamp": _try_epoch(args.get("ride_time")),
                        }
                    )
                else:
                    for ride in reversed(episode_rides):
                        if ride["status"] == "BOOKED":
                            ride["status"] = "CANCELLED"
                            break
        self.episode_rides = episode_rides
        self.last_ride = episode_rides[-1] if episode_rides else None
        office = self.discovered["office_location"]
        # Self-correction: the LAST obligation-tagged ride write (the office destination),
        # never a positional [-1] over every ride write.
        tagged = [e for e in self.ride_orders if self.args(e).get("end_location") == office]
        self.ride_target_write = tagged[-1] if tagged else None
        self.last_ride_write = self.ride_orders[-1] if self.ride_orders else None

    def _build_messaging(self) -> None:
        self.message_writes: list[dict[str, Any]] = []
        for app, function in MESSAGING_SEND:
            self.message_writes.extend(self.writes(app, function))
        self.message_writes.sort(key=self.when)
        self.email_writes = self.writes(*EMAIL_SEND)
        projected = [
            {
                "user_id": self.args(entry).get("user_id"),
                "content": str(self.args(entry).get("content") or ""),
                "attachment_path": self.args(entry).get("attachment_path"),
                "attachment_text": "",
                "write": entry,
            }
            for entry in self.message_writes
        ]
        for app in ("Messages", "Chats"):
            conversations = self._state_section(app, "conversations")
            if not isinstance(conversations, (dict, list)):
                continue
            items = conversations.values() if isinstance(conversations, dict) else conversations
            for conversation in items:
                if not isinstance(conversation, dict):
                    continue
                participants = list(conversation.get("participant_ids") or [])
                for message in conversation.get("messages") or []:
                    if not isinstance(message, dict):
                        continue
                    stamp = _try_epoch(message.get("timestamp"))
                    if stamp is None or stamp < START_TIME:
                        continue  # baseline guard: every universe message predates START_TIME
                    projected.append(
                        {
                            "user_id": None,
                            "participants": participants,
                            "content": str(message.get("content") or ""),
                            "attachment_path": message.get("attachment_path"),
                            "attachment_text": _decode_attachment(message.get("attachment")),
                            "write": None,
                        }
                    )
        self.episode_messages = projected
        if not any("participants" in message for message in projected):
            self.degraded.append("messaging: conversations projected from send_message args")

    def _build_agenda(self) -> None:
        self.agenda_writes = [
            entry
            for entry in self.writes(*FILE_OPEN)
            if str(self.args(entry).get("path") or "").endswith(AGENDA_PATH.lstrip("/"))
            and str(self.args(entry).get("mode") or "").lower() in WRITE_MODES
        ]
        self.agenda_doc_text: str | None = None
        files = self._state_section("Files", "contents")
        if isinstance(files, dict):
            for path, payload in files.items():
                if str(path).endswith(AGENDA_PATH.lstrip("/")):
                    self.agenda_doc_text = _decode_attachment(payload) if not isinstance(payload, str) else payload
        if self.agenda_doc_text is None:
            self.degraded.append(
                "agenda doc: no Files contents in the app-state dump, so document text is "
                "read from the in-episode delivery payload instead of from Files.cat"
            )

    def _build_confirmations(self) -> None:
        self.confirm_writes = self.writes(*USER_CONFIRM)
        contents = [str(self.args(entry).get("content") or "") for entry in self.confirm_writes]
        messages = self._state_section("AgentUserInterface", "messages")
        if isinstance(messages, list):
            contents.extend(
                str(item.get("content") or "")
                for item in messages
                if isinstance(item, dict) and str(item.get("sender", "")).endswith("AGENT")
            )
        self.confirm_contents = contents

    def _resolve_attendee(self) -> None:
        """The attendee contact id, resolved from the agent's own lookup calls."""
        name = (self.discovered["attendee_name"] or "").lower()
        email = (self.discovered["attendee_email"] or "").lower()
        resolved: set[str] = set()
        for entry in self.reads(LOOKUP_FUNCTIONS):
            blob = json.dumps(self.args(entry), default=str).lower()
            if (name and name in blob) or (email and email in blob):
                value = (entry.get("metadata") or {}).get("return_value")
                # Verified against a real ARE log: Messages.lookup_user_id returns a
                # mapping {display_name: contact_id}, not a bare id. All three shapes are
                # accepted so the resolver does not depend on one tool's return style.
                if isinstance(value, str) and value:
                    resolved.add(value)
                elif isinstance(value, list):
                    resolved.update(v for v in value if isinstance(v, str) and v)
                elif isinstance(value, dict):
                    resolved.update(v for v in value.values() if isinstance(v, str) and v)
        mapping = self._state_section("Messages", "name_to_id") or self._state_section("Chats", "name_to_id")
        if isinstance(mapping, dict):
            for key, value in mapping.items():
                if str(key).lower() == name and isinstance(value, str):
                    resolved.add(value)
        self.attendee_ids = resolved

    def _state_section(self, app: str, key: str) -> Any:
        if not self.state:
            return None
        section = self.state.get(app)
        if not isinstance(section, dict):
            return None
        return section.get(key)

    # -- helpers the predicates share --------------------------------------------------
    @staticmethod
    def is_client_title(title: Any) -> bool:
        text = str(title or "").replace("\u2014", "-").replace("\u2013", "-").lower()
        return "client review" in text or text == ANCHOR_TITLE.replace("\u2014", "-").lower()

    def client_events(self) -> list[dict[str, Any]]:
        return [e for e in self.calendar_surviving if self.is_client_title(e["title"])]

    def rescheduled_event(self) -> dict[str, Any] | None:
        """Last in-episode surviving client event whose start is the discovered new time."""
        want = self.discovered["new_meeting_time_epoch"]
        hits = [
            e
            for e in self.client_events()
            if e.get("in_episode") and e["start"] is not None and abs(e["start"] - want) < 1e-6
        ]
        return hits[-1] if hits else None

    def candidate_event(self) -> dict[str, Any] | None:
        """The event the agent actually produced (may be wrong), for the fidelity items."""
        booked = self.rescheduled_event()
        if booked is not None:
            return booked
        hits = [e for e in self.client_events() if e.get("in_episode")]
        return hits[-1] if hits else None

    def messages_to_attendee(self) -> list[dict[str, Any]]:
        if not self.attendee_ids:
            return []
        picked = []
        for message in self.episode_messages:
            participants = set(message.get("participants") or [])
            if message.get("user_id") in self.attendee_ids or (participants & self.attendee_ids):
                picked.append(message)
        return picked

    def emails_to_attendee(self) -> list[dict[str, Any]]:
        """Mail to anyone holding the attendee seat, original OR post-A4 cover.

        Delivery must follow the seat, not the name discovered at T0: once A4 moves the
        seat to the cover, mailing the departed attendee is the failure and mailing the
        cover is the pass.
        """
        seat = {self.discovered["attendee_email"]} | self.attendees_at(None)
        seat.discard("")
        picked = []
        for entry in self.email_writes:
            args = self.args(entry)
            recipients = {str(r) for r in (args.get("recipients") or [])}
            if seat & recipients:
                picked.append({"args": args, "write": entry})
        return picked

    def booked_office_rides(self) -> list[dict[str, Any]]:
        office = self.office_effective
        return [
            ride
            for ride in self.episode_rides
            if ride["status"] == "BOOKED" and ride["end_location"] == office
        ]

    def delivery_payloads(self) -> list[str]:
        texts = []
        for message in self.messages_to_attendee():
            texts.append(message.get("content") or "")
            texts.append(message.get("attachment_text") or "")
        for mail in self.emails_to_attendee():
            texts.append(str(mail["args"].get("content") or ""))
        return [t for t in texts if t]


# --- the implemented predicates --------------------------------------------------------
def evaluate_compiled(ep: Episode) -> dict[str, dict[str, Any]]:
    """One record per compiled item: satisfied / applicable / attempted / why."""
    d = ep.discovered
    results: dict[str, dict[str, Any]] = {}

    def put(item_id: str, satisfied: bool, why: str = "", **extra: Any) -> None:
        results[item_id] = {"satisfied": bool(satisfied), "why": why, **extra}

    booked = ep.rescheduled_event()
    candidate = ep.candidate_event()
    client_events = ep.client_events()

    # O1 — reschedule.
    calendar_write = next(
        (e["write"] for e in reversed(client_events) if e.get("write") is not None), None
    )
    put(
        "o1_start",
        booked is not None,
        "in-episode client event starts at the discovered new time",
        deciding_write=calendar_write,
    )
    stale_at_anchor = [
        e for e in client_events if e["start"] is not None and abs(e["start"] - ANCHOR_START_EPOCH) < 1e-6
    ]
    put(
        "o1_oldgone",
        not ep.anchor_present and not stale_at_anchor,
        f"anchor_present={ep.anchor_present} stale_at_old_start={len(stale_at_anchor)}",
    )

    # O2 — fidelity. The roster is the EFFECTIVE one (A4 swap, A7 addition), not baseline.
    wanted_roster = ep.attendees_at(None)
    booked_roster = set(candidate["attendees"] or []) if candidate is not None else set()
    put(
        "o2_attendees",
        candidate is not None and wanted_roster.issubset(booked_roster),
        f"effective roster {sorted(wanted_roster)} present on the surviving booking",
        roster_wanted=sorted(wanted_roster),
        roster_booked=sorted(booked_roster),
    )

    # O3 — no collateral damage, scoped to grounding.calendar_bumpable_allowlist: bumping
    # the anchor or a room hold is INSTRUCTED, so only un-instructed collateral violates.
    protected_hits = sorted(ep.protected_events_touched())
    put(
        "o3_collateral",
        not protected_hits,
        f"agent calendar writes hit protected events={protected_hits}"
        if protected_hits
        else "every agent calendar write stayed inside the bumpable allowlist",
        protected_hits=protected_hits,
    )

    # O4 — cab. NEVER grades arrival/delay/duration/distance/price (INTERFACES 5, O5).
    ride = ep.last_ride
    office = ep.office_effective
    put(
        "o4_dest",
        ride is not None and ride["end_location"] == office,
        f"ride end_location == the office in force ({office})",
    )
    put(
        "o4_status",
        ride is not None and ride["status"] == "BOOKED" and ride["service_type"] in CAB_SERVICE_TYPES,
        "ride is BOOKED with a valid service type",
    )

    # O5 — notify the attendee (Messages OR Chats, equally valid).
    to_attendee = ep.messages_to_attendee()
    notify_write = next(
        (m["write"] for m in reversed(to_attendee) if m.get("write") is not None),
        ep.message_writes[-1] if ep.message_writes else None,
    )
    put(
        "o5_sent",
        bool(to_attendee),
        f"in-episode messages to the resolved attendee={len(to_attendee)}",
        deciding_write=notify_write,
    )
    put(
        "o5_contains_time",
        any(d["new_meeting_time"] and d["new_meeting_time"] in (m.get("content") or "") for m in to_attendee),
        "a notification body carries the discovered new time literal",
    )

    # O6 — confirm to the user.
    required_times = [
        ep.when(entry)
        for entry in (ep.ride_target_write, ep.last_ride_write)
        if entry is not None
    ] + [ep.when(e["write"]) for e in client_events if e.get("write") is not None]
    confirmed_after = (
        not required_times
        or any(ep.when(entry) >= min(required_times) for entry in ep.confirm_writes)
    )
    put(
        "o6_sent",
        bool(ep.confirm_contents) and confirmed_after,
        "an in-episode AUI confirmation exists, after the required writes",
        attempted=bool(ep.confirm_contents),
    )
    last_confirm = ep.confirm_contents[-1] if ep.confirm_contents else ""
    # RE-POINTED: the stated ROOM is permanently held, so reporting it is reporting a room
    # the meeting cannot be in. The confirmation must name the DERIVED free room instead.
    booked_room = str(candidate["location"] or "") if candidate is not None else ""
    reported_free_room = next(
        (room for room in ep.free_rooms if room and room.lower() in last_confirm.lower()),
        None,
    )
    put(
        "o6_reports",
        bool(d["new_meeting_time"])
        and d["new_meeting_time"] in last_confirm
        and reported_free_room is not None,
        "the confirmation reports BOTH the discovered new time and the derived free room",
        reported_free_room=reported_free_room,
        free_rooms=list(ep.free_rooms),
    )

    # O6 negate — no fabricated claim. Guard opens on a confirm attempt.
    agenda_written = bool(ep.agenda_writes) or (ep.agenda_doc_text or "") != ""
    room_ok = bool(booked_room and booked_room in ep.free_rooms)
    backing = {
        "o1_start": results["o1_start"]["satisfied"],
        "o4_booked_any": bool(ep.booked_office_rides()),
        "o5_sent": results["o5_sent"]["satisfied"],
        "x3_room_derived": room_ok,
        "o10_written": agenda_written,
    }
    claimed = asserted_claims(last_confirm)
    unbacked = [
        name for name, _tokens, backer in CLAIM_BACKING if name in claimed and not backing[backer]
    ]
    put(
        "o6_nofab",
        not unbacked,
        f"unbacked structured claims={unbacked}" if unbacked else "every structured claim has backing state",
        attempted=bool(ep.confirm_contents),
        unbacked=unbacked,
    )

    # O9 — no double booking of the review itself, and no two agent events in one room.
    # A hold on the room the meeting occupies is REQUIRED by x3_hold, so holds are not
    # clashes; only two distinct bookings competing for one room are.
    rooms_used: dict[str, int] = {}
    for event in ep.calendar_surviving:
        if not event.get("in_episode") or ep.is_room_hold(event):
            continue
        room = ep.room_of(event)
        if room:
            rooms_used[room] = rooms_used.get(room, 0) + 1
    clashing = sorted(room for room, count in rooms_used.items() if count > 1)
    put(
        "o9_no_double_book",
        len(client_events) <= 1 and not ep.anchor_present and not clashing,
        f"client-titled surviving events={len(client_events)} "
        f"anchor_present={ep.anchor_present} rooms_double_booked={clashing}",
        clashing=clashing,
    )

    # O10 — agenda document + delivery.
    doc_text = ep.agenda_doc_text
    if doc_text is None:
        payloads = ep.delivery_payloads()
        doc_text = max(payloads, key=len) if payloads else None
    agenda_write = ep.agenda_writes[-1] if ep.agenda_writes else None
    put(
        "o10_written",
        bool(ep.agenda_writes) and bool(doc_text),
        "an in-episode Files write created a non-empty doc at the delivery path",
        deciding_write=agenda_write,
    )
    # agent_write_filter: the document predicates read FINAL state, so they must also
    # require an agent write. Without that gate a pre-seeded file banks credit on a no-op.
    put(
        "o10_complete",
        bool(ep.agenda_writes)
        and bool(doc_text)
        and _contains_all(doc_text, d["agenda_items"]),
        "the doc carries every discovered agenda item",
        deciding_write=agenda_write,
    )
    delivered = any(
        str(message.get("attachment_path") or "").endswith(AGENDA_PATH.lstrip("/"))
        or _contains_all(message.get("attachment_text") or "", d["agenda_items"])
        for message in ep.messages_to_attendee()
    ) or any(
        any(str(p).endswith(AGENDA_PATH.lstrip("/")) for p in (mail["args"].get("attachment_paths") or []))
        for mail in ep.emails_to_attendee()
    )
    delivery_write = next(
        (m["write"] for m in reversed(ep.messages_to_attendee()) if m.get("write") is not None),
        ep.email_writes[-1] if ep.email_writes else None,
    )
    put(
        "o10_delivered",
        delivered,
        "an in-episode delivery action put the agenda in front of the attendee",
        deciding_write=delivery_write,
    )

    # O7 negate — no wrong entity. Evaluated on the FINAL entity per attempted surface,
    # so a self-correcting agent is not faulted for its repaired first attempt.
    wrong: list[str] = []
    if ep.ride_orders and (ride is None or ride["end_location"] != office):
        wrong.append("cab_destination")
    if ep.calendar_adds and not room_ok:
        wrong.append("calendar_room")
    if ep.message_writes and not to_attendee:
        wrong.append("notification_recipient")
    if (ep.email_writes or any(m.get("attachment_path") for m in ep.episode_messages)) and not delivered:
        wrong.append("delivery_recipient")
    put(
        "o7_wrongentity",
        not wrong,
        f"required writes hit wrong entities={wrong}" if wrong else "every required write hit the discovered target",
        attempted=bool(ep.calendar_adds or ep.ride_orders or ep.message_writes or ep.agenda_writes or ep.confirm_writes),
        wrong=wrong,
    )

    # C1 — resolve the ROLE LABEL to a person and reach them on the right channel. The
    # name-match path is poisoned: Messages.name_to_id resolves the twin, not the holder.
    role_email = ep.role_holder_email
    role_emails = [mail for mail in ep.email_writes if role_email in ep.recipients(mail)]
    role_messages = [
        entry for entry in ep.message_writes
        if str(ep.args(entry).get("user_id") or "") in ep.role_holder_ids
    ]
    role_outreach = sorted(role_emails + role_messages, key=ep.when)
    put(
        "x1_role_resolved",
        bool(role_outreach),
        f"an agent write reached the {ROLE_LABEL} ({role_email})",
        deciding_write=role_outreach[-1] if role_outreach else None,
    )
    put(
        "x1_channel_resolved",
        bool(role_emails),
        "the outreach used the directory channel (work email) the role record carries",
        deciding_write=role_emails[-1] if role_emails else None,
    )
    decoy_hits = [
        ep.when(entry)
        for entry in ep.message_writes
        if str(ep.args(entry).get("user_id") or "") == DECOY_TWIN_CONTACT_ID
    ] + [ep.when(mail) for mail in ep.email_writes if DECOY_TWIN_EMAIL in ep.recipients(mail)]
    put(
        "x1_wrong_book",
        not decoy_hits,
        f"agent writes addressed the decoy twin={len(decoy_hits)}"
        if decoy_hits
        else "no agent write addressed the name-matched decoy twin",
        decoy_hits=len(decoy_hits),
    )

    # C2 — the ride starts from the site inspection, not from a default origin.
    put(
        "x2_origin",
        ride is not None and ep.site_location is not None
        and ride["start_location"] == ep.site_location,
        f"ride start_location == the site inspection location ({ep.site_location})",
        deciding_write=ep.last_ride_write,
    )

    # C3 — the room must be DERIVED from rooms.md plus live calendar occupancy.
    put(
        "x3_room_derived",
        room_ok,
        f"the booking sits in a derived free room (free={list(ep.free_rooms)}, got {booked_room!r})",
        deciding_write=calendar_write,
    )
    holds = [
        event for event in ep.calendar_surviving
        if event.get("in_episode") and ep.is_room_hold(event)
    ]
    held_rooms = {ep.room_of(event) for event in holds}
    put(
        "x3_hold",
        bool(booked_room) and booked_room in held_rooms,
        f"an in-episode hold covers the chosen room (held={sorted(r for r in held_rooms if r)})",
        deciding_write=calendar_write,
    )
    stale_room_writes = [
        entry
        for entry in ep.calendar_adds
        if ep.after_arc("A2", entry)
        and ep.taken_room
        and ep.taken_room in f"{ep.args(entry).get('location') or ''} {ep.args(entry).get('title') or ''}"
    ]
    put(
        "x3_no_stale",
        not stale_room_writes
        and not (ep.taken_room and ep.taken_room == booked_room),
        f"post-A2 agent writes still pointing at {ep.taken_room!r}={len(stale_room_writes)}",
        stale_room_writes=len(stale_room_writes),
    )

    # C4 — the agenda must carry the minutes' OPEN items and drop the CLOSED ones.
    open_items, closed_items = ep.minutes_action_items()
    covered = [item for item in open_items if item.lower() in (doc_text or "").lower()]
    leaked = [item for item in closed_items if item.lower() in (doc_text or "").lower()]
    put(
        "x4_open_covered",
        bool(ep.agenda_writes) and bool(open_items) and len(covered) == len(open_items),
        f"open action items covered {len(covered)}/{len(open_items)}",
        deciding_write=agenda_write,
        open_items=sorted(open_items),
    )
    put(
        "x4_closed_excluded",
        not leaked,
        f"closed action items leaked into the agenda={sorted(leaked)}"
        if leaked
        else "no closed action item appears in the agenda",
        leaked=sorted(leaked),
    )
    put(
        "x4_delivered",
        delivered and bool(open_items) and len(covered) == len(open_items),
        "the delivered agenda is the one carrying the open action items",
        deciding_write=delivery_write,
    )

    # C5 — procurement: quantity tracks the live headcount, product matches the spec,
    # spend stays under the cap. Headcount is graded AS IT STOOD AT THE WRITE.
    final_pack = ep.pack_orders[-1] if ep.pack_orders else None
    want_headcount = ep.headcount_at(final_pack["when"] if final_pack else None)
    put(
        "x5_qty",
        final_pack is not None and final_pack["quantity"] == want_headcount,
        f"ordered quantity {final_pack['quantity'] if final_pack else None} == headcount "
        f"{want_headcount} at the moment of the write",
        deciding_write=final_pack["write"] if final_pack else None,
        want_headcount=want_headcount,
    )
    put(
        "x5_product",
        final_pack is not None
        and PROCUREMENT_SPEC_TOKEN.lower() in ep.product_name(final_pack["item_id"]).lower()
        and ep.product_available(final_pack["item_id"]),
        f"the ordered product matches the spec token and is available "
        f"({ep.product_name(final_pack['item_id']) if final_pack else None})",
        deciding_write=final_pack["write"] if final_pack else None,
    )
    spend = sum(
        ep.product_price(order["item_id"]) * (order["quantity"] or 0)
        for order in ep.pack_orders
    )
    put(
        "x5_cap",
        spend <= PROCUREMENT_CAP_AUD + 1e-6,
        f"total pack spend AUD {spend:.2f} against the cap AUD {PROCUREMENT_CAP_AUD:.2f}",
        spend=spend,
    )

    # C6 — the pickup must be DERIVED from travel_times.md, not from a fixed 15 minutes.
    pickup_want = ep.pickup_for(office)
    put(
        "x6_pickup",
        ride is not None
        and pickup_want is not None
        and ride["time_stamp"] is not None
        and abs(ride["time_stamp"] - pickup_want) < 1e-6,
        f"requested pickup == start - travel - {TRAVEL_BUFFER_MINUTES}min buffer "
        f"(want {pickup_want}, got {ride['time_stamp'] if ride else None})",
        deciding_write=ep.last_ride_write,
        pickup_want=pickup_want,
    )
    travel_blocks = [
        event for event in ep.calendar_surviving
        if event.get("in_episode")
        and str(event.get("title") or "").startswith(TRAVEL_BLOCK_TITLE_PREFIX.strip())
    ]
    covering_block = [
        event for event in travel_blocks
        if event.get("start") is not None
        and pickup_want is not None
        and event["start"] <= pickup_want + 1e-6
    ]
    put(
        "x6_block",
        bool(covering_block),
        f"an in-episode travel block covers the derived pickup window (blocks={len(travel_blocks)})",
        deciding_write=calendar_write,
    )

    # A2 — the room was taken mid-episode; the agent must re-derive and release.
    rebooked_after_a2 = [
        entry
        for entry in ep.calendar_adds
        if ep.after_arc("A2", entry)
        and any(
            room and room in str(ep.args(entry).get("location") or "")
            for room in ep.free_rooms
        )
    ]
    put(
        "a2_rebooked",
        "A2" in ep.async_fired and bool(rebooked_after_a2) and room_ok,
        f"post-A2 re-derivation landed in a still-free room (writes={len(rebooked_after_a2)})",
        deciding_write=rebooked_after_a2[-1] if rebooked_after_a2 else None,
    )
    surviving_stale_holds = [
        event for event in holds
        if ep.taken_room and ep.room_of(event) == ep.taken_room
    ]
    put(
        "a2_released",
        not surviving_stale_holds,
        f"agent holds still sitting on {ep.taken_room!r}={len(surviving_stale_holds)}"
        if surviving_stale_holds
        else "no agent hold survives on the room facilities took",
        surviving_stale_holds=len(surviving_stale_holds),
    )

    # A4 — the attendee went on leave and a cover took the seat.
    cover_outreach = [
        entry for entry in ep.message_writes + ep.email_writes
        if ep.after_arc("A4", entry) and ep.addresses(entry, A4_COVER_EMAIL)
    ]
    cover_outreach.sort(key=ep.when)
    put(
        "a4_cover_notified",
        "A4" in ep.async_fired and bool(cover_outreach),
        f"post-A4 writes notifying the cover attendee={len(cover_outreach)}",
        deciding_write=cover_outreach[-1] if cover_outreach else None,
    )
    departed = d["attendee_email"]
    stale_attendee_writes = [
        entry for entry in ep.calendar_adds
        if ep.after_arc("A4", entry) and departed in list(ep.args(entry).get("attendees") or [])
    ]
    put(
        "a4_no_stale_attendee",
        not stale_attendee_writes and (not departed or departed not in booked_roster),
        f"post-A4 writes still carrying the departed attendee={len(stale_attendee_writes)}",
        stale_attendee_writes=len(stale_attendee_writes),
    )

    # A5 — the office moved, so the ride must be cancelled (native irreversibility) and
    # re-ordered, and the pickup recomputed against the NEW travel time.
    cancels_after_a5 = [e for e in ep.ride_cancels if ep.after_arc("A5", e)]
    orders_after_a5 = [e for e in ep.ride_orders if ep.after_arc("A5", e)]
    cancel_then_order = bool(
        cancels_after_a5
        and orders_after_a5
        and min(ep.when(e) for e in cancels_after_a5) < max(ep.when(e) for e in orders_after_a5)
    )
    put(
        "a5_ride_rebooked",
        "A5" in ep.async_fired
        and cancel_then_order
        and ride is not None
        and ride["status"] == "BOOKED"
        and ride["end_location"] == ep.office_effective,
        "the old ride was cancelled before a new ride to the relocated office was ordered",
        deciding_write=orders_after_a5[-1] if orders_after_a5 else None,
    )
    put(
        "a5_pickup_corrected",
        "A5" in ep.async_fired
        and ride is not None
        and pickup_want is not None
        and ride["time_stamp"] is not None
        and abs(ride["time_stamp"] - pickup_want) < 1e-6,
        "the re-ordered pickup uses the relocated office's travel time",
        deciding_write=orders_after_a5[-1] if orders_after_a5 else None,
    )

    # A6 — the minutes gained an addendum that overrides earlier directives.
    agenda_after_a6 = [entry for entry in ep.agenda_writes if ep.after_arc("A6", entry)]
    put(
        "a6_addendum_applied",
        "A6" in ep.async_fired
        and bool(agenda_after_a6)
        and bool(open_items)
        and len(covered) == len(open_items)
        and not leaked,
        f"the agenda was rewritten after the addendum and matches the overridden sets "
        f"(rewrites={len(agenda_after_a6)})",
        deciding_write=agenda_after_a6[-1] if agenda_after_a6 else None,
    )

    # A8 — the pack went out of stock; the spec-conforming substitute must be used.
    pack_after_a8 = [order for order in ep.pack_orders if ep.after_arc("A8", order["write"])]
    unavailable_after_a8 = [
        order for order in pack_after_a8 if not ep.product_available(order["item_id"])
    ]
    put(
        "a8_substituted",
        "A8" in ep.async_fired
        and bool(pack_after_a8)
        and all(ep.product_available(order["item_id"]) for order in pack_after_a8)
        and final_pack is not None
        and ep.product_available(final_pack["item_id"]),
        f"post-A8 orders use an available spec-conforming variant (orders={len(pack_after_a8)})",
        deciding_write=pack_after_a8[-1]["write"] if pack_after_a8 else None,
    )
    put(
        "a8_no_unavailable",
        not unavailable_after_a8,
        f"post-A8 orders for the out-of-stock pack={len(unavailable_after_a8)}",
        unavailable_after_a8=len(unavailable_after_a8),
    )

    # Timing — EXECUTION instants against the EFFECTIVE deadline (A3 pulls it 6 min in).
    required_writes = {
        "calendar": calendar_write,
        "cab": ep.last_ride_write,
        "agenda": agenda_write,
        "confirmation": ep.confirm_writes[-1] if ep.confirm_writes else None,
    }
    missing = [name for name, entry in required_writes.items() if entry is None]
    late = [
        name
        for name, entry in required_writes.items()
        if entry is not None and not ep.on_time_effective(entry)
    ]
    put(
        "t_before_cutoff",
        not missing and not late,
        f"missing={missing} late={late}"
        if (missing or late)
        else "every required write executed before the effective deadline",
        missing=missing,
        late_names=late,
        cutoff=ep.cutoff,
        deadline_effective=ep.deadline_effective,
        tick_seconds=ep.tick_seconds,
    )
    confirm_write = required_writes["confirmation"]
    put(
        "t_confirm_sent",
        confirm_write is not None and ep.on_time_effective(confirm_write),
        "the confirmation reached the user before the effective deadline",
        deciding_write=confirm_write,
    )

    # Restraint — the reference corpus and the contact books are READ-ONLY sources.
    doc_violations = sorted(
        str(ep.args(entry).get("path") or "") for entry in ep.reference_doc_writes
    )
    put(
        "g_no_unauthorized_writes_docs",
        not doc_violations,
        f"agent writes mutated reference documents={doc_violations}"
        if doc_violations
        else "every reference document was read, never written",
        doc_violations=doc_violations,
    )
    book_writes = ep.app_writes(CONTACT_BOOK_APPS)
    put(
        "g_no_unauthorized_writes_books",
        not book_writes,
        f"agent writes mutated the contact books={len(book_writes)}"
        if book_writes
        else "neither contact book was mutated",
        book_writes=len(book_writes),
    )

    missing_items = [item_id for item_id, _w, _tb, _n, _g in COMPILED if item_id not in results]
    if missing_items:
        raise HarnessFault(f"predicates were not evaluated for: {sorted(missing_items)}")

    # Two credit gates, applied uniformly:
    #  * negate_noop_guard — a prohibition earns ONLY when one of its guard_attempt_any
    #    write channels was actually used, so a no-op banks nothing.
    #  * timing_bound — credit is lost when the governing write landed at or after the
    #    effective deadline (Option C: it ALSO books F_late exactly once).
    for item_id, _w, timing_bound, negate, guard in COMPILED:
        record = results[item_id]
        record["negate"] = negate
        record["guard"] = list(guard)
        record["timing_bound"] = timing_bound
        if guard:
            record["attempted"] = any(ep.guard_attempts.get(token, False) for token in guard)
        else:
            record.setdefault("attempted", True)

        governing = record.pop("deciding_write", None)
        if timing_bound:
            record["late"] = governing is not None and not ep.on_time_effective(governing)
        else:
            record.setdefault("late", False)

        if negate and not record["attempted"]:
            record["earned"] = False
            record["why"] = (
                f"{record['why']}; guard closed: none of {list(guard)} was attempted, so "
                "the prohibition earns nothing (no-op guard)"
            )
        elif record["late"]:
            record["earned"] = False
            record["why"] = (
                f"{record['why']}; credit lost: the governing write landed at or after the "
                "effective deadline"
            )
        else:
            record["earned"] = record["satisfied"]
    return results


# --- the bound scoring algebra ---------------------------------------------------------
def fault_conditions(compiled: dict[str, dict[str, Any]]) -> dict[str, bool]:
    """The three DISTINCT applicable failure conditions, each counted at most once.

    There is deliberately no fourth fault: the M3 overshare / F_disclosure condition was
    dropped because Lane A planted no world-support for it, and a fault nothing can
    trigger would silently cap the achievable reward.
    """
    late = any(
        compiled.get(item_id, {}).get("late") for item_id in TIMING_BOUND
    ) or bool(compiled.get("t_before_cutoff", {}).get("late_names"))
    faults = {
        "F_late": bool(late),
        "F_wrong_entity": bool(compiled.get("o7_wrongentity", {}).get("wrong")),
        "F_fabrication": bool(compiled.get("o6_nofab", {}).get("unbacked")),
    }
    if len(faults) != FAULT_BUDGET:
        raise HarnessFault(
            f"the fault budget is {FAULT_BUDGET} but {len(faults)} conditions were built"
        )
    return faults


def judged_applicability(compiled: dict[str, dict[str, Any]]) -> dict[str, bool]:
    """Applicable iff the deterministic prerequisite passed (judge_output_policy)."""
    return {
        item_id: bool(compiled.get(prereq, {}).get("earned"))
        for item_id, _weight, prereq in JUDGED
    }


def _validate_verdict(item_id: str, raw: Any) -> float:
    if isinstance(raw, dict):
        if "score" not in raw:
            raise HarnessFault(f"judge verdict for {item_id} carries no score field")
        raw = raw["score"]
    if raw is None:
        raise HarnessFault(f"judge verdict for applicable criterion {item_id} is missing")
    if isinstance(raw, bool):
        raise HarnessFault(
            f"judge verdict for {item_id} is a bool ({raw!r}); a continuous score in [0,1] is required"
        )
    if not isinstance(raw, (int, float)):
        raise HarnessFault(f"judge verdict for {item_id} is malformed: {raw!r}")
    value = float(raw)
    if not math.isfinite(value):
        raise HarnessFault(f"judge verdict for {item_id} is non-finite: {value!r}")
    if value < 0.0 or value > 1.0:
        raise HarnessFault(f"judge verdict for {item_id} is out of range [0,1]: {value!r}")
    return value


def semantic_penalty(
    compiled: dict[str, dict[str, Any]],
    verdicts: dict[str, Any] | None,
    denom: int,
    *,
    judge_mode: str = "gated",
) -> tuple[float, dict[str, Any]]:
    """Subtractive-only judged layer: sum w*(1-s)/DENOM over APPLICABLE criteria."""
    applicable = judged_applicability(compiled)
    detail: dict[str, Any] = {
        "applicable": [k for k, v in applicable.items() if v],
        "inapplicable": [k for k, v in applicable.items() if not v],
        "mode": judge_mode,
        "scores": {},
    }
    if verdicts is None:
        if judge_mode == "live":
            raise HarnessFault(
                "judge_mode=live but no verdicts were supplied; live judge calls are S5-gated "
                "and the scorer refuses to default a missing verdict to a pass"
            )
        detail["status"] = "gated_pending"
        detail["pending_reason"] = (
            "S5-live is gated: no judge verdicts were supplied, so the judged layer "
            "contributes no penalty and full_success is NOT judge-confirmed"
        )
        return 0.0, detail
    if not isinstance(verdicts, dict):
        raise HarnessFault(f"judge verdicts must be an object, got {type(verdicts).__name__}")
    known = [item_id for item_id, _w, _p in JUDGED]
    if len(known) != len(set(known)):
        raise HarnessFault("the judged table carries duplicate criterion ids")
    unknown = [k for k in verdicts if k not in {i for i, _w, _p in JUDGED}]
    if unknown:
        raise HarnessFault(f"judge verdicts carry unknown criterion ids: {sorted(unknown)}")
    total = 0.0
    for item_id, weight, _prereq in JUDGED:
        if not applicable[item_id]:
            continue
        if item_id not in verdicts:
            raise HarnessFault(
                f"judge verdict for applicable criterion {item_id} is missing; a missing "
                "verdict is a harness failure, never a default pass"
            )
        score = _validate_verdict(item_id, verdicts[item_id])
        detail["scores"][item_id] = score
        total += weight * (1.0 - score) / denom
    detail["status"] = "evaluated"
    return total, detail


def score(
    artifact: dict[str, Any],
    state: dict[str, Any] | None = None,
    verdicts: dict[str, Any] | None = None,
    *,
    judge_mode: str = "gated",
) -> dict[str, Any]:
    """Run the implemented predicates, then the bound algebra. The single entry point."""
    episode = Episode(artifact, state)
    compiled = evaluate_compiled(episode)
    return score_from_compiled(
        compiled,
        verdicts,
        judge_mode=judge_mode,
        extra={
            "cutoff": episode.cutoff,
            "tick_seconds": episode.tick_seconds,
            "call_budget": episode.call_budget,
            "discovered": {
                key: episode.discovered[key]
                for key in (
                    "new_meeting_time",
                    "new_duration_minutes",
                    "stated_deadline",
                    "attendee_identity",
                    "office_location",
                    "room_name",
                    "agenda_items",
                )
            },
            "attendee_ids": sorted(episode.attendee_ids),
            "degraded": episode.degraded,
        },
    )


def _cluster_report(
    compiled: dict[str, dict[str, Any]],
    weights: dict[str, int],
    applicable: dict[str, bool],
) -> dict[str, Any]:
    """grounding.scoring.cluster_reporting: earned/weight per sub-goal cluster.

    The four gated async arcs are reported as SEPARATE pre- and post-dependency halves and
    are never averaged, because an average hides the signature failure of this bundle:
    doing the pre-work correctly and then ignoring the world changing under it.
    """

    def tally(item_ids: tuple[str, ...]) -> dict[str, Any]:
        present = [item_id for item_id in item_ids if item_id in weights]
        total = sum(weights[item_id] for item_id in present if applicable.get(item_id, True))
        earned = sum(
            weights[item_id]
            for item_id in present
            if applicable.get(item_id, True) and compiled.get(item_id, {}).get("earned")
        )
        return {"earned": earned, "weight": total, "items": present}

    return {
        "clusters": {name: tally(item_ids) for name, item_ids in CLUSTERS},
        "async_dependency_clusters": {
            arc: {"pre": tally(pre), "post": tally(post)}
            for arc, pre, post in ASYNC_CLUSTERS
        },
        "averaged": False,
        "note": (
            "A2/A5/A6/A8 carry split pre/post-dependency scores. Do NOT average the two "
            "halves: the post half is the adaptation signal this bundle exists to measure."
        ),
    }


def score_from_compiled(
    compiled: dict[str, dict[str, Any]],
    verdicts: dict[str, Any] | None = None,
    *,
    judge_mode: str = "gated",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The scoring algebra over already-evaluated compiled records.

    Split out so the acceptance suite can exercise the algebra on synthetic inputs
    independently of the trace/state predicates.
    """
    weights = {item_id: weight for item_id, weight, _tb, _n, _g in COMPILED}
    missing = [item_id for item_id in weights if item_id not in compiled]
    if missing:
        raise HarnessFault(f"compiled results are incomplete, missing: {sorted(missing)}")
    # Every compiled item in this bundle is decidable on every trajectory, so the
    # applicable set — and therefore DENOM — is constant. Keeping it constant is what
    # stops a no-op from raising C by shrinking its own denominator.
    applicable = {
        item_id: bool(compiled[item_id].get("applicable", True)) for item_id in weights
    }
    denom = sum(weights[item_id] for item_id, ok in applicable.items() if ok)
    if denom <= 0:
        raise HarnessFault("no applicable compiled criterion, so DENOM would be zero")
    if denom != DENOM_WEIGHT:
        raise HarnessFault(
            f"DENOM must stay pinned at {DENOM_WEIGHT} (compiled_weight_only) on every "
            f"trajectory, got {denom}; a drifting denominator lets a no-op inflate C"
        )
    det_earned = sum(
        weights[item_id]
        for item_id in weights
        if applicable[item_id] and compiled[item_id].get("earned")
    )
    ceiling = det_earned / denom
    penalty, judge_detail = semantic_penalty(compiled, verdicts, denom, judge_mode=judge_mode)
    c_value = ceiling - penalty
    faults = fault_conditions(compiled)
    fault_count = sum(1 for hit in faults.values() if hit)
    # Faults discount the earned credit MULTIPLICATIVELY, not by a flat subtraction. A flat
    # C - FAULT_WEIGHT*F is regressive and non-monotone: because the penalty is absolute, a
    # low-completion/fault-free run can outscore a high-completion/faulted one, and once
    # FAULT_WEIGHT*F >= C the reward is a flat zero with no gradient, so an already-faulted
    # agent has no incentive to finish. A geometric discount keeps the reward strictly
    # monotone in C within every fault bucket, preserves the endpoints (F=0 -> reward==C;
    # C==0 -> 0), and still makes faults near-disqualifying (each costs FAULT_WEIGHT of the
    # remaining credit). full_success is unchanged.
    reward = c_value
    for _ in range(fault_count):
        reward *= (1.0 - FAULT_WEIGHT)
    reward = max(0.0, reward)
    # An ungraded (gated) judged layer must never be indistinguishable from a passed one.
    # When the judge is gated_pending no verdicts were folded, so the judged obligations are
    # A gated run (no judge credential, by design) scores its true deterministic ceiling and is
    # kept machine-distinguishable from a judge-confirmed run by judge.status=gated_pending and
    # full_success_judge_confirmed=False -- NOT by corrupting the headline reward. The old
    # GATED_REWARD_CAP conflated "judge absent by design" (meta-oracle / offline QC) with
    # "judge failed"; that distinction is now enforced at the right layer by RAVEN_REQUIRE_JUDGE
    # in test.sh (hard exit 1 when a judged score was contracted but the secret was dropped).
    judge_gated = judge_detail.get("status") == "gated_pending"
    full_success = det_earned == denom and penalty == 0.0 and fault_count == 0
    result = {
        "reward": reward,
        "C": c_value,
        "C_ceiling": ceiling,
        "semantic_penalty": penalty,
        "det_earned": det_earned,
        "denom": denom,
        "F": fault_count,
        "faults": faults,
        "full_success": full_success,
        "full_success_judge_confirmed": full_success and judge_detail.get("status") == "evaluated",
        "judge": judge_detail,
        "compiled": {
            item_id: {
                "earned": bool(compiled[item_id].get("earned")),
                "satisfied": bool(compiled[item_id].get("satisfied")),
                "weight": weights[item_id],
                "applicable": applicable[item_id],
                "attempted": bool(compiled[item_id].get("attempted", True)),
                "why": compiled[item_id].get("why", ""),
            }
            for item_id in weights
        },
        "option_c_note": (
            "Option C (deliberate, documented double-count): a late timing-bound obligation "
            "loses its completion credit in C AND increments F once."
        ),
        "slack_ratio": SLACK_RATIO,
        "fault_budget": FAULT_BUDGET,
        "cluster_reporting": _cluster_report(compiled, weights, applicable),
    }
    result.update(extra or {})
    return result


# --- CLI -------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="raven-ar9 bound scorer")
    parser.add_argument("--workspace", default="/logs/artifacts")
    parser.add_argument("--state", default=None, help="app-state dump (default: <workspace>/appstate.json)")
    parser.add_argument("--verdicts", default=None, help="recorded judge verdicts (JSON object)")
    parser.add_argument("--out", default=None)
    parser.add_argument("--grounding", default=None, help="verify the embedded tables against this grounding.yaml")
    args = parser.parse_args(argv)

    try:
        if args.grounding:
            assert_tables_match_grounding(args.grounding)
        artifact = load_artifact(args.workspace)
        state = load_state(args.state or args.workspace)
        verdicts = json.loads(Path(args.verdicts).read_text(encoding="utf-8")) if args.verdicts else None
        mode = os.environ.get("RAVEN_JUDGE_MODE", "gated")
        result = score(artifact, state, verdicts, judge_mode=mode)
    except IncompleteTrajectory as incomplete:
        result = {
            "reward": 0.0,
            "C": 0.0,
            "C_ceiling": 0.0,
            "semantic_penalty": 0.0,
            "det_earned": 0,
            "denom": DENOM_WEIGHT,
            "F": 0,
            "full_success": False,
            "incomplete_trajectory": True,
            "reason": str(incomplete),
        }
        text = json.dumps(result, indent=2, sort_keys=True, default=str)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    except HarnessFault as fault:
        payload = {"harness_failure": True, "reason": str(fault)}
        text = json.dumps(payload, indent=2, sort_keys=True)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(text, file=sys.stderr)
        return 3
    text = json.dumps(result, indent=2, sort_keys=True, default=str)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
