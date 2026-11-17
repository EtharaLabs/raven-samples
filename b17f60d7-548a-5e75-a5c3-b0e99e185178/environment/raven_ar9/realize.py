from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone

ARCHETYPE = "ar9_temporal_deadline"
SCENARIO_ID = "raven_ar9_temporal_deadline_incident"

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

START_TIME = 1729150200.0
# FORGE hardening (Lane H-A): PART 8 mandates the 1800s episode grow to 5400s so the
# nine async events A1..A9 (last at t+3450) all land inside the episode.
DURATION_SECONDS = 5400
TIME_INCREMENT_SECONDS = 1

T_EMAIL = 120.0

UNIVERSE_APP_COUNT = 12
BASELINE_RIDE_COUNT = 60

USER_EMAIL = "mara.ellis@example.org"
CLIENT_SENDER = "dana.whitfield@catchmentpartners.example"
CLIENT_NAME = "Dana Whitfield"
CLIENT_SUBJECT = "Reschedule: catchment telemetry review (action needed)"

ANCHOR_EVENT_ID = "raven_ar9_client_review"
ANCHOR_TITLE = "Client Review \u2014 Catchment Telemetry Program"
ANCHOR_START_EPOCH = 1729155600.0
ANCHOR_END_EPOCH = 1729159200.0
ANCHOR_TAG = "client"
ANCHOR_LOCATION = "Regional Water Authority Depot, Rocklea, Brisbane"
ANCHOR_DESCRIPTION = (
    "Quarterly program review with Catchment Partners. Agenda pack to be circulated "
    "before the session."
)
ANCHOR_SECOND_ATTENDEE = "priya.nair@example.com"

CAB_SERVICE_TYPE = "Default"
CAB_LEAD_SECONDS = 900
CAB_START_LOCATION = "14 Beeston Street, Teneriffe QLD 4005"

AGENDA_PATH = "/Documents/client_review_agenda.md"

NEW_TIME_OFFSETS = (5400, 7200, 9000, 10800, 16200, 19800)
DURATION_MINUTES_POOL = (30, 45, 50, 75, 90, 120)
# FORGE hardening (Lane H-A): the legacy pool (780..1380) expired the confirmation
# window before A3 (t+1500) even fired, so A3..A9 all landed post-deadline. The pool
# is moved out so that the post-A3 deadline (offset - 360) still exceeds A9 at t+3450
# and stays inside DURATION_SECONDS. Published discovery value: stated_deadline.
CUTOFF_OFFSETS = (3900, 4080, 4260, 4440, 4620, 4800)

ATTENDEE_POOL = (
    ("Maya Bennett", "contact_0000", "maya.bennett@example.com"),
    ("Megan Callaghan", "contact_0100", "megan.callaghan@example.com"),
    ("Mei Tan", "contact_0123", "mei.tan@example.com"),
    ("Morgan Reid", "contact_0128", "morgan.reid@example.com"),
)

OFFICE_POOL = (
    "Seqwater Head Office, 240 Margaret Street, Brisbane QLD 4000",
    "Catchment Partners, Level 9, 180 Ann Street, Brisbane QLD 4000",
    "Regional Water Authority Rocklea Depot, Rocklea QLD",
)

ROOM_POOL = (
    "Catchment Room 2",
    "Wivenhoe Boardroom",
    "Oxley Meeting Room",
    "Brisbane River Room",
)

AGENDA_POOL = (
    "Flood gauge telemetry backlog",
    "Q4 abstraction licence renewals",
    "Wivenhoe release schedule review",
    "Rocklea depot sensor replacement plan",
    "Hydrometric data retention policy",
    "Oxley Creek station uptime report",
)

AGENDA_ITEM_COUNT = 3

LABEL_NEW_MEETING_TIME = "NEW_MEETING_TIME"
LABEL_NEW_DURATION_MINUTES = "NEW_DURATION_MINUTES"
LABEL_STATED_DEADLINE = "CONFIRM_BY"
LABEL_ATTENDEE = "ATTENDEE"
LABEL_OFFICE_LOCATION = "OFFICE_LOCATION"
LABEL_ROOM = "ROOM"
LABEL_AGENDA = "AGENDA"

LABEL_RE = re.compile(r"^(?P<label>[A-Z_]+):[ \t]*(?P<value>.*?)[ \t]*$", re.MULTILINE)
ATTENDEE_RE = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^<>@\s]+@[^<>@\s]+)>$")
AGENDA_ITEM_RE = re.compile(r"^-[ \t]+(?P<item>\S.*?)[ \t]*$", re.MULTILINE)

CUTOFF_EVENT_ID = "raven_ar9_cutoff"
CLIENT_EMAIL_EVENT_ID = "raven_ar9_client_email"


@dataclass(frozen=True)
class RealizedState:
    seed: int
    new_meeting_time: str
    new_meeting_time_epoch: float
    new_duration_minutes: int
    new_meeting_end: str
    new_meeting_end_epoch: float
    stated_deadline: str
    stated_deadline_epoch: float
    cutoff_offset_seconds: int
    attendee_identity: str
    attendee_contact_id: str
    attendee_email: str
    office_location: str
    room_name: str
    agenda_items: tuple[str, ...]
    cab_pickup_time: str
    cab_pickup_epoch: float
    anchor_attendees: tuple[str, ...]


def to_stamp(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime(DATETIME_FORMAT)


def to_epoch(stamp: str) -> float:
    return (
        datetime.strptime(stamp, DATETIME_FORMAT).replace(tzinfo=timezone.utc).timestamp()
    )


def _draw(seed: int, field: str, modulus: int) -> int:
    digest = hashlib.sha256(f"raven-ar9-are:{int(seed)}:{field}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % modulus


def _draw_agenda(seed: int) -> tuple[str, ...]:
    remaining = list(AGENDA_POOL)
    chosen: list[str] = []
    for slot in range(AGENDA_ITEM_COUNT):
        chosen.append(remaining.pop(_draw(seed, f"agenda{slot}", len(remaining))))
    return tuple(chosen)


def derive(seed: int) -> RealizedState:
    seed = int(seed)
    start_epoch = ANCHOR_START_EPOCH + NEW_TIME_OFFSETS[_draw(seed, "when", len(NEW_TIME_OFFSETS))]
    minutes = DURATION_MINUTES_POOL[_draw(seed, "duration", len(DURATION_MINUTES_POOL))]
    end_epoch = start_epoch + minutes * 60
    cutoff_offset = CUTOFF_OFFSETS[_draw(seed, "cutoff", len(CUTOFF_OFFSETS))]
    deadline_epoch = START_TIME + cutoff_offset
    name, contact_id, email = ATTENDEE_POOL[_draw(seed, "attendee", len(ATTENDEE_POOL))]
    pickup_epoch = start_epoch - CAB_LEAD_SECONDS
    return RealizedState(
        seed=seed,
        new_meeting_time=to_stamp(start_epoch),
        new_meeting_time_epoch=start_epoch,
        new_duration_minutes=minutes,
        new_meeting_end=to_stamp(end_epoch),
        new_meeting_end_epoch=end_epoch,
        stated_deadline=to_stamp(deadline_epoch),
        stated_deadline_epoch=deadline_epoch,
        cutoff_offset_seconds=cutoff_offset,
        attendee_identity=name,
        attendee_contact_id=contact_id,
        attendee_email=email,
        office_location=OFFICE_POOL[_draw(seed, "office", len(OFFICE_POOL))],
        room_name=ROOM_POOL[_draw(seed, "room", len(ROOM_POOL))],
        agenda_items=_draw_agenda(seed),
        cab_pickup_time=to_stamp(pickup_epoch),
        cab_pickup_epoch=pickup_epoch,
        anchor_attendees=(email, ANCHOR_SECOND_ATTENDEE),
    )


def client_email_body(realized: RealizedState) -> str:
    agenda_block = "\n".join(f"- {item}" for item in realized.agenda_items)
    return (
        f"Hi Mara,\n"
        f"\n"
        f"Our board moved and we have to shift today's program review. Everything below is "
        f"final from our side.\n"
        f"\n"
        f"{LABEL_NEW_MEETING_TIME}: {realized.new_meeting_time}\n"
        f"{LABEL_NEW_DURATION_MINUTES}: {realized.new_duration_minutes}\n"
        f"{LABEL_STATED_DEADLINE}: {realized.stated_deadline}\n"
        f"{LABEL_ATTENDEE}: {realized.attendee_identity} <{realized.attendee_email}>\n"
        f"{LABEL_OFFICE_LOCATION}: {realized.office_location}\n"
        f"{LABEL_ROOM}: {realized.room_name}\n"
        f"{LABEL_AGENDA}:\n"
        f"{agenda_block}\n"
        f"\n"
        f"All times are UTC. Keep the existing invitee list on the booking, send a car so we "
        f"start on time, get the agenda pack to our attendee, and confirm back to me.\n"
        f"\n"
        f"{CLIENT_NAME}\n"
        f"Catchment Partners\n"
    )


def parse_client_email(body: str) -> dict:
    labels = {m.group("label"): m.group("value") for m in LABEL_RE.finditer(body)}
    agenda_start = body.find(f"{LABEL_AGENDA}:")
    agenda_tail = body[agenda_start:] if agenda_start >= 0 else ""
    items = [m.group("item") for m in AGENDA_ITEM_RE.finditer(agenda_tail)]
    attendee_raw = labels.get(LABEL_ATTENDEE, "")
    attendee_match = ATTENDEE_RE.match(attendee_raw)
    new_time = labels.get(LABEL_NEW_MEETING_TIME, "")
    minutes = int(labels[LABEL_NEW_DURATION_MINUTES]) if LABEL_NEW_DURATION_MINUTES in labels else 0
    deadline = labels.get(LABEL_STATED_DEADLINE, "")
    parsed = {
        "new_meeting_time": new_time,
        "new_duration_minutes": minutes,
        "stated_deadline": deadline,
        "attendee_identity": attendee_match.group("name") if attendee_match else "",
        "attendee_email": attendee_match.group("email") if attendee_match else "",
        "office_location": labels.get(LABEL_OFFICE_LOCATION, ""),
        "room_name": labels.get(LABEL_ROOM, ""),
        "agenda_items": items,
    }
    if new_time:
        parsed["new_meeting_time_epoch"] = to_epoch(new_time)
        parsed["new_meeting_end"] = to_stamp(to_epoch(new_time) + minutes * 60)
        parsed["cab_pickup_time"] = to_stamp(to_epoch(new_time) - CAB_LEAD_SECONDS)
    if deadline:
        parsed["stated_deadline_epoch"] = to_epoch(deadline)
    return parsed


def agenda_document(realized: RealizedState) -> str:
    lines = [
        f"# {ANCHOR_TITLE}",
        "",
        f"Time: {realized.new_meeting_time} UTC ({realized.new_duration_minutes} minutes)",
        f"Room: {realized.room_name}",
        f"Location: {realized.office_location}",
        "",
        "## Agenda",
        "",
    ]
    lines.extend(f"{n}. {item}" for n, item in enumerate(realized.agenda_items, start=1))
    lines.append("")
    return "\n".join(lines)


HARDEN_LANE = "H-A"

ROLE_LABEL = "Depot Facilities Coordinator"
ROLE_HOLDER_NAME = "Nadia Forster"
ROLE_HOLDER_FIRST_NAME = "Nadia"
ROLE_HOLDER_LAST_NAME = "Forster"
ROLE_HOLDER_CONTACT_ID = "contact_0301"
ROLE_HOLDER_EMAIL = "nadia.forster@seqwater.example.org"
ROLE_HOLDER_PHONE = "+61 7 3015 0301"
ROLE_HOLDER_DIRECTORY_NAME = "Nadia Forster (Depot Facilities)"
ROLE_HOLDER_ADDRESS = "Seqwater Rocklea Depot, 1 Sherwood Road, Rocklea QLD 4106"

DECOY_TWIN_CONTACT_ID = "contact_0302"
DECOY_TWIN_NAME = "Nadia Forster"
DECOY_TWIN_EMAIL = "nadia.forster@quickmail.example.com"
DECOY_TWIN_PHONE = "+61 4 1702 0302"
DECOY_TWIN_JOB = "Ceramics studio volunteer"
DECOY_TWIN_ADDRESS = "27 Hawthorne Road, Bulimba QLD 4171"

SITE_INSPECTION_EVENT_ID = "raven_ar9_site_inspection"
SITE_INSPECTION_TITLE = "Site inspection \u2014 pre-review walkthrough"
SITE_INSPECTION_TAG = "fieldwork"
SITE_INSPECTION_DESCRIPTION = (
    "Pre-review walkthrough with the depot crew. Travel to the client office departs "
    "from this site."
)
SITE_INSPECTION_START_LEAD_SECONDS = 10800
SITE_INSPECTION_END_LEAD_SECONDS = 5400
SITE_LOCATION_POOL = (
    "Oxley Creek Intake Screens, 88 Sherwood Road, Rocklea QLD 4106",
    "Enoggera Reservoir Valve House, Mount Nebo Road, The Gap QLD 4061",
    "Mount Crosby Eastbank Pump Station, Mount Crosby Road, Karana Downs QLD 4306",
)

FACILITIES_DIR = "/Work/facilities"
ROOMS_DOC_PATH = "/Work/facilities/rooms.md"
PROCUREMENT_DOC_PATH = "/Work/facilities/procurement_rules.md"
TRAVEL_DOC_PATH = "/Work/facilities/travel_times.md"
MINUTES_DIR = "/Work/minutes"
MINUTES_DOC_PATH = "/Work/minutes/2024-10-03-telemetry-review-minutes.md"

ROOM_CAPACITIES = {
    "Catchment Room 2": 10,
    "Wivenhoe Boardroom": 24,
    "Oxley Meeting Room": 8,
    "Brisbane River Room": 12,
}
LARGEST_ROOM = "Wivenhoe Boardroom"
ROOM_ROTATION = tuple(room for room in ROOM_POOL if room != LARGEST_ROOM)
ROOM_HOLD_WINDOW_SECONDS = 7200
ROOM_HOLD_TAG = "room-hold"
ROOM_HOLD_OWNER = "facilities@seqwater.example.org"
ROOM_HOLD_TITLE_PREFIX = "Room hold \u2014 "
ROOM_HOLD_EVENT_ID_PREFIX = "raven_ar9_room_hold_"

MINUTES_THREAD_SENDER = "owen.brady@catchmentpartners.example"
MINUTES_THREAD_NAME = "Owen Brady"
MINUTES_THREAD_SUBJECT = "Minutes from the 3 Oct telemetry review"
MINUTES_THREAD_EMAIL_ID = "raven_ar9_minutes_thread"
MINUTES_THREAD_OFFSET_SECONDS = -1209600
MINUTES_ITEM_POOL = (
    "Telemetry backlog triage rota",
    "Gauge board recalibration schedule",
    "Depot sensor spares procurement",
    "Winter abstraction reporting template",
    "Fish ladder monitoring handover",
    "Pump station SCADA patch window",
)
MINUTES_OPEN_COUNT = 3
MINUTES_CLOSED_COUNT = 2
MINUTES_OPEN_PREFIX = "OPEN:"
MINUTES_CLOSED_PREFIX = "CLOSED:"
MINUTES_ADDENDUM_HEADING = "## Addendum (issued after circulation)"

PACK_PRODUCT_ID = "product_90001"
PACK_PRODUCT_NAME = "Catchment Review Delegate Pack"
PACK_ITEM_ID = "product_90001_v0"
PACK_UNIT_PRICE = 18.5
SUBSTITUTE_PRODUCT_ID = "product_90002"
SUBSTITUTE_PRODUCT_NAME = "Catchment Review Delegate Pack Recycled Edition"
SUBSTITUTE_ITEM_ID = "product_90002_v0"
SUBSTITUTE_UNIT_PRICE = 19.25
PROCUREMENT_SPEC_TOKEN = "Catchment Review Delegate Pack"
PROCUREMENT_CAP_AUD = 70.0

TRAVEL_BUFFER_MINUTES = 15
TRAVEL_MINUTES_MATRIX = (
    (22, 41, 12),
    (37, 29, 48),
    (46, 38, 33),
)
TRAVEL_BLOCK_TITLE_PREFIX = "Travel \u2014 "

A3_DEADLINE_SHIFT_SECONDS = -360
A4_COVER_NAME = "Priya Nair"
A4_COVER_EMAIL = ANCHOR_SECOND_ATTENDEE
A4_COVER_CONTACT_ID = "contact_0001"
A7_ATTENDEE_NAME = "Tomas Kowal"
A7_ATTENDEE_EMAIL = "tomas.kowal@catchmentpartners.example"

ASYNC_EVENT_OFFSETS = {
    "A1": 120.0,
    "A2": 900.0,
    "A3": 1500.0,
    "A4": 2100.0,
    "A5": 2550.0,
    "A6": 3000.0,
    "A7": 2700.0,
    "A8": 3150.0,
    "A9": 3450.0,
}
ASYNC_EVENT_IDS = {
    "A1": CLIENT_EMAIL_EVENT_ID,
    "A2": "raven_ar9_a2_room_taken",
    "A3": "raven_ar9_a3_deadline_pulled",
    "A4": "raven_ar9_a4_attendee_on_leave",
    "A5": "raven_ar9_a5_office_relocated",
    "A6": "raven_ar9_a6_minutes_addendum",
    "A7": "raven_ar9_a7_second_attendee",
    "A8": "raven_ar9_a8_pack_out_of_stock",
    "A9": "raven_ar9_a9_duration_cut",
}
ASYNC_GATE_IDS = {
    "A2": "raven_ar9_a2_gate",
    "A5": "raven_ar9_a5_gate",
    "A6": "raven_ar9_a6_gate",
    "A8": "raven_ar9_a8_gate",
}
ASYNC_GATE_TICK_SECONDS = 15


def room_hold_event_id(room: str) -> str:
    slug = room.lower().replace(" ", "_")
    return f"{ROOM_HOLD_EVENT_ID_PREFIX}{slug}"


def _draw_permutation(seed: int, field: str, pool: tuple[str, ...]) -> tuple[str, ...]:
    remaining = list(pool)
    ordered: list[str] = []
    for slot in range(len(pool)):
        ordered.append(remaining.pop(_draw(seed, f"{field}{slot}", len(remaining))))
    return tuple(ordered)


def _rotation_pick(seed: int, field: str, exclude: frozenset[str]) -> str:
    size = len(ROOM_ROTATION)
    offset = _draw(seed, field, size)
    for index in range(size):
        candidate = ROOM_ROTATION[(offset + index) % size]
        if candidate not in exclude:
            return candidate
    raise ValueError(f"no admissible room outside {sorted(exclude)}")


def _duration_after_a9(seed: int, minutes: int) -> int:
    smaller = tuple(d for d in DURATION_MINUTES_POOL if d < minutes)
    if smaller:
        return smaller[_draw(seed, "a9duration", len(smaller))]
    larger = tuple(d for d in DURATION_MINUTES_POOL if d > minutes)
    return larger[_draw(seed, "a9duration", len(larger))]


def _office_after_a5(seed: int, office: str) -> str:
    index = OFFICE_POOL.index(office)
    step = 1 + _draw(seed, "a5office", len(OFFICE_POOL) - 1)
    return OFFICE_POOL[(index + step) % len(OFFICE_POOL)]


def travel_minutes(site_location: str, office_location: str) -> int:
    return TRAVEL_MINUTES_MATRIX[SITE_LOCATION_POOL.index(site_location)][
        OFFICE_POOL.index(office_location)
    ]


def pickup_epoch_for(start_epoch: float, site_location: str, office_location: str) -> float:
    minutes = travel_minutes(site_location, office_location) + TRAVEL_BUFFER_MINUTES
    return float(start_epoch) - minutes * 60


def room_holds(rooms: tuple[str, ...], start_epoch: float) -> tuple[tuple[str, str, float, float], ...]:
    end_epoch = float(start_epoch) + ROOM_HOLD_WINDOW_SECONDS
    return tuple(
        (room_hold_event_id(room), room, float(start_epoch), end_epoch) for room in rooms
    )


def free_rooms_for_window(
    holds: tuple[tuple[str, str, float, float], ...],
    window_start: float,
    window_end: float,
) -> tuple[str, ...]:
    held = {
        room
        for _, room, hold_start, hold_end in holds
        if hold_start < window_end and hold_end > window_start
    }
    return tuple(room for room in ROOM_POOL if room not in held)


@dataclass(frozen=True)
class HardenedState:
    seed: int
    site_location: str
    site_start_epoch: float
    site_end_epoch: float
    free_room_baseline: str
    free_room_after_a2: str
    held_rooms_baseline: tuple[str, ...]
    held_rooms_after_a2: tuple[str, ...]
    room_holds_baseline: tuple[tuple[str, str, float, float], ...]
    room_holds_after_a2: tuple[tuple[str, str, float, float], ...]
    minutes_open_baseline: tuple[str, ...]
    minutes_closed_baseline: tuple[str, ...]
    minutes_reserve_item: str
    minutes_a6_opened: str
    minutes_a6_closed: str
    minutes_open_after_a6: tuple[str, ...]
    minutes_closed_after_a6: tuple[str, ...]
    travel_minutes_baseline: int
    pickup_epoch_baseline: float
    pickup_time_baseline: str
    office_after_a5: str
    travel_minutes_after_a5: int
    pickup_epoch_after_a5: float
    pickup_time_after_a5: str
    deadline_epoch_after_a3: float
    deadline_after_a3: str
    duration_after_a9: int
    meeting_end_epoch_after_a9: float
    meeting_end_after_a9: str
    attendee_emails_baseline: tuple[str, ...]
    attendee_emails_after_a4: tuple[str, ...]
    attendee_emails_after_a7: tuple[str, ...]
    headcount_baseline: int
    headcount_final: int
    pack_unit_price_final: float
    pack_spend_final: float
    async_times: dict[str, float]


def derive_hardened(realized: RealizedState) -> HardenedState:
    seed = int(realized.seed)
    start_epoch = float(realized.new_meeting_time_epoch)

    site_location = SITE_LOCATION_POOL[_draw(seed, "site", len(SITE_LOCATION_POOL))]
    site_start_epoch = start_epoch - SITE_INSPECTION_START_LEAD_SECONDS
    site_end_epoch = start_epoch - SITE_INSPECTION_END_LEAD_SECONDS

    free_baseline = _rotation_pick(seed, "freeroom", frozenset({realized.room_name}))
    free_after_a2 = _rotation_pick(
        seed, "freeroom", frozenset({realized.room_name, free_baseline})
    )
    held_baseline = tuple(room for room in ROOM_POOL if room != free_baseline)
    held_after_a2 = tuple(room for room in ROOM_POOL if room != free_after_a2)

    ordered_items = _draw_permutation(seed, "minutes", MINUTES_ITEM_POOL)
    open_baseline = ordered_items[:MINUTES_OPEN_COUNT]
    closed_baseline = ordered_items[
        MINUTES_OPEN_COUNT : MINUTES_OPEN_COUNT + MINUTES_CLOSED_COUNT
    ]
    reserve_item = ordered_items[MINUTES_OPEN_COUNT + MINUTES_CLOSED_COUNT]
    a6_closed = open_baseline[_draw(seed, "a6close", len(open_baseline))]
    open_after_a6 = tuple(
        item for item in open_baseline if item != a6_closed
    ) + (reserve_item,)
    closed_after_a6 = closed_baseline + (a6_closed,)

    travel_baseline = travel_minutes(site_location, realized.office_location)
    pickup_baseline = pickup_epoch_for(start_epoch, site_location, realized.office_location)
    office_a5 = _office_after_a5(seed, realized.office_location)
    travel_a5 = travel_minutes(site_location, office_a5)
    pickup_a5 = pickup_epoch_for(start_epoch, site_location, office_a5)

    deadline_a3 = float(realized.stated_deadline_epoch) + A3_DEADLINE_SHIFT_SECONDS
    duration_a9 = _duration_after_a9(seed, realized.new_duration_minutes)
    end_a9 = start_epoch + duration_a9 * 60

    attendees_baseline = tuple(realized.anchor_attendees)
    attendees_a4 = (A4_COVER_EMAIL,)
    attendees_a7 = attendees_a4 + (A7_ATTENDEE_EMAIL,)
    headcount_baseline = 1 + len(attendees_baseline)
    headcount_final = 1 + len(attendees_a7)

    return HardenedState(
        seed=seed,
        site_location=site_location,
        site_start_epoch=site_start_epoch,
        site_end_epoch=site_end_epoch,
        free_room_baseline=free_baseline,
        free_room_after_a2=free_after_a2,
        held_rooms_baseline=held_baseline,
        held_rooms_after_a2=held_after_a2,
        room_holds_baseline=room_holds(held_baseline, start_epoch),
        room_holds_after_a2=room_holds(held_after_a2, start_epoch),
        minutes_open_baseline=open_baseline,
        minutes_closed_baseline=closed_baseline,
        minutes_reserve_item=reserve_item,
        minutes_a6_opened=reserve_item,
        minutes_a6_closed=a6_closed,
        minutes_open_after_a6=open_after_a6,
        minutes_closed_after_a6=closed_after_a6,
        travel_minutes_baseline=travel_baseline,
        pickup_epoch_baseline=pickup_baseline,
        pickup_time_baseline=to_stamp(pickup_baseline),
        office_after_a5=office_a5,
        travel_minutes_after_a5=travel_a5,
        pickup_epoch_after_a5=pickup_a5,
        pickup_time_after_a5=to_stamp(pickup_a5),
        deadline_epoch_after_a3=deadline_a3,
        deadline_after_a3=to_stamp(deadline_a3),
        duration_after_a9=duration_a9,
        meeting_end_epoch_after_a9=end_a9,
        meeting_end_after_a9=to_stamp(end_a9),
        attendee_emails_baseline=attendees_baseline,
        attendee_emails_after_a4=attendees_a4,
        attendee_emails_after_a7=attendees_a7,
        headcount_baseline=headcount_baseline,
        headcount_final=headcount_final,
        pack_unit_price_final=SUBSTITUTE_UNIT_PRICE,
        pack_spend_final=round(headcount_final * SUBSTITUTE_UNIT_PRICE, 2),
        async_times={
            key: START_TIME + offset for key, offset in ASYNC_EVENT_OFFSETS.items()
        },
    )


def rooms_document() -> str:
    lines = [
        "# Depot meeting rooms",
        "",
        "Canonical bookable rooms. A room counts as free for a window only when no",
        "Calendar event overlaps that window in the room.",
        "",
        "| Room | Capacity | Notes |",
        "| --- | --- | --- |",
    ]
    for room in ROOM_POOL:
        note = "Largest room; standing executive hold." if room == LARGEST_ROOM else "General use."
        lines.append(f"| {room} | {ROOM_CAPACITIES[room]} | {note} |")
    lines.extend(
        [
            "",
            "## Holding a room",
            "",
            f"1. Room holds are granted only by the {ROLE_LABEL}.",
            "2. The staff directory is InternalContacts. The coordinator is the single",
            f"   directory entry whose job field reads `{ROLE_LABEL}`.",
            "   Contact search does not index job titles, so page the directory with",
            "   get_contacts to find the entry.",
            "3. Send the hold request from the Messages app. Email is not monitored for",
            "   room holds.",
            "4. Address the message to the coordinator's staff directory id, which is the",
            "   InternalContacts contact id. The personal address book is not the staff",
            "   directory and its ids are not valid staff directory ids; a namesake there",
            "   cannot grant a hold.",
            "5. If the room named by a client is already held for the window, take the",
            "   single remaining free canonical room from the table above.",
            "",
        ]
    )
    return "\n".join(lines)


def procurement_document() -> str:
    lines = [
        "# Delegate pack procurement rules",
        "",
        f"1. Order exactly one `{PROCUREMENT_SPEC_TOKEN}` per confirmed attendee of the",
        "   review, counting the organiser.",
        "2. Count attendees from the Calendar booking as it stands when you order.",
        f"3. Total spend on packs must not exceed AUD {PROCUREMENT_CAP_AUD:.2f}.",
        f"4. If the specified pack is unavailable, order the single available catalog",
        f"   product whose name also contains `{PROCUREMENT_SPEC_TOKEN}`.",
        "5. Never order a pack that the catalog reports as unavailable.",
        "",
    ]
    return "\n".join(lines)


def travel_document() -> str:
    lines = [
        "# Depot to office travel times",
        "",
        "Scheduled road travel in minutes, door to door. These figures are contractual",
        "and are used for pickup planning. Do not substitute live traffic estimates.",
        "",
        "| From site | " + " | ".join(f"To: {office}" for office in OFFICE_POOL) + " |",
        "| --- |" + " --- |" * len(OFFICE_POOL),
    ]
    for index, site in enumerate(SITE_LOCATION_POOL):
        cells = " | ".join(str(value) for value in TRAVEL_MINUTES_MATRIX[index])
        lines.append(f"| {site} | {cells} |")
    lines.extend(
        [
            "",
            "## Pickup rule",
            "",
            f"Pickup time = meeting start time minus travel minutes minus a",
            f"{TRAVEL_BUFFER_MINUTES} minute buffer. Block the interval from pickup to",
            "meeting start on the calendar.",
            "",
        ]
    )
    return "\n".join(lines)


def minutes_document(
    open_items: tuple[str, ...],
    closed_items: tuple[str, ...],
    addendum: tuple[tuple[str, str], ...] = (),
) -> str:
    lines = [
        "# Catchment telemetry review minutes, 3 October",
        "",
        "## Action register",
        "",
    ]
    for item in open_items:
        lines.append(f"{MINUTES_OPEN_PREFIX} {item}")
    for item in closed_items:
        lines.append(f"{MINUTES_CLOSED_PREFIX} {item}")
    if addendum:
        lines.extend(["", MINUTES_ADDENDUM_HEADING, ""])
        for prefix, item in addendum:
            lines.append(f"{prefix} {item}")
    lines.extend(
        [
            "",
            "Only items marked OPEN carry forward to the next review agenda.",
            "",
        ]
    )
    return "\n".join(lines)


def minutes_thread_body() -> str:
    return (
        f"Mara,\n"
        f"\n"
        f"Minutes from the 3 October session are filed at {MINUTES_DOC_PATH}.\n"
        f"The action register there is the only authoritative list.\n"
        f"\n"
        f"{MINUTES_THREAD_NAME}\n"
        f"Catchment Partners\n"
    )


def client_email_body_hardened(realized: RealizedState) -> str:
    pointer_block = (
        f"A few things you will have to look up rather than read off this mail.\n"
        f"\n"
        f"* Loop in our {ROLE_LABEL}. The staff directory carries the role; the personal\n"
        f"  address book has a namesake who does not work for us.\n"
        f"* I am coming straight from the site inspection that is already on your\n"
        f"  calendar that morning. Use that event's location as the pickup point.\n"
        f"* If the room below is already held, follow {ROOMS_DOC_PATH}.\n"
        f"* Owen's earlier thread points at the minutes file. Carry forward the open\n"
        f"  items only.\n"
        f"* Delegate packs per {PROCUREMENT_DOC_PATH}.\n"
        f"* Work the pickup time out from {TRAVEL_DOC_PATH}, not from a traffic app.\n"
        f"\n"
    )
    original = client_email_body(realized)
    marker = f"{LABEL_NEW_MEETING_TIME}:"
    split_at = original.index(marker)
    return original[:split_at] + pointer_block + original[split_at:]
