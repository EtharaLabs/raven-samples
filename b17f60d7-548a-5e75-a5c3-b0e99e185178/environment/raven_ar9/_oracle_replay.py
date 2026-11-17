# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 75e76ad5fdc1c20433fc50803c285f8cb69ca3c139ea082b87adb476602d96f0
# FORGE-CANARY-END
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_ENV_ROOT = _PACKAGE_ROOT / "environment"
_SOLUTION_ROOT = _PACKAGE_ROOT / "solution"
for _root in (_ENV_ROOT, _SOLUTION_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from raven_ar9 import _oracle_truth as truth
from are.simulation.apps.email_client import EmailFolderName
from are.simulation.environment import Environment, EnvironmentConfig
from are.simulation.types import CompletedEvent, EventMetadata, EventRegisterer, EventType
from raven_ar9 import realize as realize_mod
from raven_ar9 import statedump
from raven_ar9.clock import DeterministicClock
from raven_ar9.realize import (
    AGENDA_PATH,
    ANCHOR_EVENT_ID,
    ANCHOR_TAG,
    ANCHOR_TITLE,
    ATTENDEE_POOL,
    CAB_LEAD_SECONDS,
    CAB_SERVICE_TYPE,
    CAB_START_LOCATION,
    CLIENT_SENDER,
    DURATION_SECONDS,
    MINUTES_CLOSED_PREFIX,
    MINUTES_DOC_PATH,
    MINUTES_OPEN_PREFIX,
    OFFICE_POOL,
    PACK_ITEM_ID,
    PROCUREMENT_DOC_PATH,
    ROOM_HOLD_OWNER,
    ROOM_HOLD_TAG,
    ROOM_HOLD_TITLE_PREFIX,
    ROOM_POOL,
    ROOMS_DOC_PATH,
    START_TIME,
    T_EMAIL,
    TIME_INCREMENT_SECONDS,
    TRAVEL_BLOCK_TITLE_PREFIX,
    TRAVEL_DOC_PATH,
    agenda_document,
    parse_client_email,
    to_epoch,
    to_stamp,
)
from raven_ar9.scenario import (
    A2_SUBJECT,
    A3_SUBJECT,
    A4_SUBJECT,
    A5_SUBJECT,
    A6_SUBJECT,
    A7_SUBJECT,
    A8_SUBJECT,
    A9_SUBJECT,
    RavenAR9,
    client_email,
    cutoff_marker_email,
)

# score.py keys each arc off a log entry carrying the arc marker event_id (the posted
# notice emails are suppressed from the log), so the driver must emit these ENV markers.
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
ROLE_LABEL = "Depot Facilities Coordinator"

DEFAULT_EVENTLOG = "logs/artifacts/eventlog.json"

STEP_SECONDS = 20.0
UNTICKED_STEPS = frozenset({"advance", "deliver_discovery", "cutoff"})


class SimClock:
    # TimeManager.time_passed() only honours a pause while pause_passed_time is TRUTHY, so a
    # 0.0 silently resumes wall-clock time. Keep it non-zero and steer sim time through
    # pause_offset, which is the only fully deterministic lever on a paused TimeManager.
    def __init__(self, time_manager, start_time: float):
        time_manager.reset(start_time)
        time_manager.pause()
        if not time_manager.pause_passed_time:
            time_manager.pause_passed_time = 1e-9
        self._time_manager = time_manager
        self._base = float(start_time) + float(time_manager.pause_passed_time)
        self.set(start_time)

    def set(self, epoch: float) -> None:
        self._time_manager.pause_offset = float(epoch) - self._base

    def now(self) -> float:
        return self._time_manager.time()

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("simulated time cannot move backwards")
        self.set(self.now() + float(seconds))

    def advance_to(self, epoch: float) -> None:
        self.advance(float(epoch) - self.now())


class OracleRun:
    def __init__(self, seed: int | None = None):
        self.realized = truth.realize(seed)
        RavenAR9._injected_realized = self.realized
        self.scenario = RavenAR9()
        self.scenario.initialize()
        self.apps = {app.name: app for app in self.scenario.apps}
        self.baseline_calendar_ids = set(self.apps["Calendar"].events.keys())
        self.env = Environment(
            config=EnvironmentConfig(
                start_time=START_TIME,
                duration=DURATION_SECONDS,
                time_increment_in_seconds=TIME_INCREMENT_SECONDS,
                oracle_mode=False,
                queue_based_loop=False,
                exit_when_no_events=False,
            )
        )
        self.env.register_apps(self.scenario.apps)
        self.clock = SimClock(self.env.time_manager, START_TIME)
        # The grader reads the quantum and start instant from a top-level `clock` manifest
        # (tests/score.py: clock.tick_seconds / clock.start_time). In the delivered path
        # raven_ar9.server.flush() attaches DeterministicClock.manifest(); the author-side
        # driver attaches the same block from the same class so the standalone repro scores
        # without hand-supplying constants. Built after SimClock pins sim time to START_TIME
        # so start_time matches the server's. The driver steers time via SimClock rather than
        # meter(), so calls/ledger stay empty here; the grader does not read them.
        self.deterministic_clock = DeterministicClock(self.env)
        self.discovered: dict = {}
        self.attendee_id: str | None = None
        self.created_event_id: str | None = None
        self.anchor_event_id: str | None = None
        self.preserved_attendees: list[str] = []
        self.ride_ids: list[str] = []
        self.hardened = realize_mod.derive_hardened(self.realized)
        self.fired: set[str] = set()
        self.role_holder_id: str | None = None
        self.role_holder_email: str | None = None
        self.chosen_room: str | None = None
        self.canonical_rooms: list[str] = []
        self.free_rooms: list[str] = []
        self.booked_attendees: list[str] = []

    def _calendar(self):
        return self.apps["Calendar"]

    def _cat(self, path: str) -> str:
        raw = self.apps["Files"].cat(path)
        return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)

    def _mark_fired(self, key: str, event_time: float) -> None:
        marker = CompletedEvent(
            event_type=EventType.ENV,
            action=None,
            event_time=float(event_time),
            event_id=ASYNC_EVENT_IDS[key],
            metadata=EventMetadata(return_value=None),
        )
        self.env.add_to_log(marker)
        self.fired.add(key)

    def step_advance(self, seconds: float | None = None, to: float | None = None) -> None:
        if to is not None:
            self.clock.advance_to(float(to))
        else:
            self.clock.advance(float(seconds or 0))

    def step_deliver_discovery(self) -> None:
        self.clock.advance_to(START_TIME + T_EMAIL)
        self.apps["Emails"].add_email(client_email(self.realized), EmailFolderName.INBOX)

    def step_cutoff(self) -> None:
        self.clock.advance_to(self.realized.stated_deadline_epoch)
        self.apps["Emails"].add_email(cutoff_marker_email(), EmailFolderName.INBOX)

    def _notice_email(self, subject: str, body: str) -> None:
        from raven_ar9.scenario import _notice
        from raven_ar9.realize import ASYNC_EVENT_OFFSETS

        offsets = {
            A2_SUBJECT: "A2", A3_SUBJECT: "A3", A4_SUBJECT: "A4", A5_SUBJECT: "A5",
            A6_SUBJECT: "A6", A7_SUBJECT: "A7", A8_SUBJECT: "A8", A9_SUBJECT: "A9",
        }
        with EventRegisterer.disable():
            self.apps["Emails"].add_email(
                _notice(subject, body, ASYNC_EVENT_OFFSETS[offsets[subject]]),
                EmailFolderName.INBOX,
            )

    def step_fire_async(self, key: str) -> None:
        when = self.hardened.async_times[key]
        self.clock.advance_to(when)
        mutator = getattr(self, f"_mutate_{key.lower()}")
        mutator()
        self._mark_fired(key, when)

    def _mutate_a2(self) -> None:
        h = self.hardened
        cal = self._calendar()
        with EventRegisterer.disable():
            for event_id, room, _start, _end in h.room_holds_baseline:
                if room == h.free_room_after_a2 and event_id in cal.events:
                    del cal.events[event_id]
            from are.simulation.apps.calendar import CalendarEvent

            for event_id, room, start_epoch, end_epoch in h.room_holds_after_a2:
                if event_id in cal.events:
                    continue
                cal.events[event_id] = CalendarEvent(
                    event_id=event_id,
                    title=f"{ROOM_HOLD_TITLE_PREFIX}{room}",
                    start_datetime=start_epoch,
                    end_datetime=end_epoch,
                    tag=ROOM_HOLD_TAG,
                    description=f"Standing facilities hold on {room}.",
                    location=room,
                    attendees=[ROOM_HOLD_OWNER],
                )
        self._notice_email(
            A2_SUBJECT,
            f"Facilities have taken {h.free_room_baseline} for your window and released "
            f"another room. Re-derive the free canonical room from {ROOMS_DOC_PATH} "
            f"against the calendar as it stands now.",
        )

    def _mutate_a3(self) -> None:
        h = self.hardened
        self._notice_email(
            A3_SUBJECT,
            f"The confirmation window moves 6 minutes earlier. New confirm-by is "
            f"{h.deadline_after_a3} UTC.",
        )

    def _mutate_a4(self) -> None:
        self._notice_email(
            A4_SUBJECT,
            f"{self.realized.attendee_identity} went on leave this morning. "
            f"priya.nair@example.com covers the session, so "
            f"{self.realized.attendee_email} should come off the booking. The agenda "
            f"pack goes to the covering attendee.",
        )

    def _mutate_a5(self) -> None:
        h = self.hardened
        self._notice_email(
            A5_SUBJECT,
            f"We have moved this session to {h.office_after_a5}. Any ride you already "
            f"booked is for the wrong destination; cancel it and rebook from the "
            f"inspection site, and re-derive the pickup from {TRAVEL_DOC_PATH}.",
        )

    def _mutate_a6(self) -> None:
        h = self.hardened
        with EventRegisterer.disable():
            with self.apps["Files"].open(MINUTES_DOC_PATH, "w") as handle:
                handle.write(
                    realize_mod.minutes_document(
                        h.minutes_open_baseline,
                        h.minutes_closed_baseline,
                        addendum=(
                            (MINUTES_OPEN_PREFIX, h.minutes_a6_opened),
                            (MINUTES_CLOSED_PREFIX, h.minutes_a6_closed),
                        ),
                    )
                )
        self._notice_email(
            A6_SUBJECT,
            f"An addendum has been appended to {MINUTES_DOC_PATH}. One item opens and "
            f"one item closes. The addendum overrides the register above it.",
        )

    def _mutate_a7(self) -> None:
        self._notice_email(
            A7_SUBJECT,
            "Please add tomas.kowal@catchmentpartners.example to the booking. He is new "
            "and is not in either address book yet, so you will have to add him before "
            "you can message him.",
        )

    def _mutate_a8(self) -> None:
        with EventRegisterer.disable():
            self.apps["ShoppingApp"].update_item(item_id=PACK_ITEM_ID, new_availability=False)
        self._notice_email(
            A8_SUBJECT,
            f"The supplier has pulled the standard delegate pack. Follow the "
            f"substitution rule in {PROCUREMENT_DOC_PATH}.",
        )

    def _mutate_a9(self) -> None:
        h = self.hardened
        self._notice_email(
            A9_SUBJECT,
            f"We only need {h.duration_after_a9} minutes now, not "
            f"{self.realized.new_duration_minutes}. The start time is unchanged, so the "
            f"session now ends {h.meeting_end_after_a9} UTC.",
        )

    def step_read_discovery(self) -> None:
        inbox = self.apps["Emails"].folders[EmailFolderName.INBOX]
        candidates = [mail for mail in inbox.emails if mail.sender == CLIENT_SENDER]
        briefs = [mail for mail in candidates if "NEW_MEETING_TIME:" in (mail.content or "")]
        if not briefs:
            raise RuntimeError("discovery email absent from inbox; nothing to solve from")
        briefs.sort(key=lambda mail: mail.timestamp)
        self.discovered = parse_client_email(briefs[-1].content)

    def step_lookup_attendee(self) -> None:
        name = self.discovered["attendee_identity"]
        hits = self.apps["Messages"].lookup_user_id(name)
        if name not in hits:
            raise RuntimeError(f"attendee {name!r} not resolvable in Messages contacts")
        self.attendee_id = hits[name]

    def step_resolve_role(self) -> None:
        directory = self.apps["InternalContacts"].get_state().get("contacts") or {}
        for contact_id, record in directory.items():
            if ROLE_LABEL.lower() in str(record.get("job") or "").lower():
                self.role_holder_id = str(record.get("contact_id") or contact_id)
                self.role_holder_email = str(record.get("email") or "")
                return
        raise RuntimeError(f"no InternalContacts record carries the {ROLE_LABEL!r} job")

    def step_page_role_holder(self) -> None:
        if self.role_holder_id is None or not self.role_holder_email:
            raise RuntimeError("role holder not resolved; run resolve_role first")
        room = self.chosen_room or self.discovered["room_name"]
        request = (
            f"Hold request: please hold {room} for the catchment telemetry review on "
            f"{self.discovered['new_meeting_time']} UTC."
        )
        self.apps["Messages"].send_message(user_id=self.role_holder_id, content=request)
        self.apps["Emails"].send_email(
            recipients=[self.role_holder_email],
            subject="Room hold \u2014 catchment telemetry review",
            content=request,
        )

    def step_add_second_attendee(self) -> None:
        self.apps["Messages"].add_users(["Tomas Kowal"])

    def step_derive_free_room(self) -> None:
        canonical = self._parse_rooms()
        start = self.discovered["new_meeting_time_epoch"]
        end = self.hardened.meeting_end_epoch_after_a9
        occupied: set[str] = set()
        for event in self._calendar().events.values():
            e_start = float(getattr(event, "start_datetime", 0) or 0)
            e_end = float(getattr(event, "end_datetime", 0) or 0)
            if not (e_start < end and e_end > start):
                continue
            blob = f"{getattr(event, 'location', '') or ''} {getattr(event, 'title', '') or ''}"
            for room in canonical:
                if room in blob:
                    occupied.add(room)
        stated = self.discovered["room_name"]
        free = [r for r in canonical if r not in occupied and r != stated]
        if not free:
            raise RuntimeError("no free canonical room derivable from rooms.md + calendar")
        self.chosen_room = free[0]
        self.canonical_rooms = list(canonical)
        self.free_rooms = list(free)

    def step_force_occupied_room(self) -> None:
        # Control/alternate helper: swap the derived free room for a canonical room that is
        # NOT free (occupied in the calendar window or the stated-but-unavailable room), so
        # the next booking lands in a wrong room. Derived from live state, never a literal.
        if self.chosen_room is None:
            raise RuntimeError("free room not derived; run derive_free_room first")
        wrong = next((r for r in self.canonical_rooms if r not in self.free_rooms), None)
        if wrong is None:
            raise RuntimeError("every canonical room is free; no wrong room to force")
        self.chosen_room = wrong

    def _parse_rooms(self) -> list[str]:
        rooms: list[str] = []
        for line in self._cat(ROOMS_DOC_PATH).splitlines():
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2 and cells[1].isdigit():
                rooms.append(cells[0])
        return rooms or list(ROOM_POOL)

    def _travel_minutes(self, site: str, office: str) -> int:
        header: list[str] | None = None
        for line in self._cat(TRAVEL_DOC_PATH).splitlines():
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if not cells:
                continue
            if cells[0].startswith("To:") or (header is None and any(c.startswith("To:") for c in cells)):
                header = [c[len("To:"):].strip() if c.startswith("To:") else c for c in cells]
                continue
            if header is None or cells[0] == "---" or all(c == "---" for c in cells):
                continue
            if cells[0] in site or site in cells[0]:
                for idx, col in enumerate(header[1:], start=1):
                    if (col in office or office in col) and idx < len(cells) and cells[idx].isdigit():
                        return int(cells[idx])
        raise RuntimeError(f"travel minutes not derivable for {site!r} -> {office!r}")

    def _site_location(self) -> str:
        for event in self._calendar().events.values():
            if event.event_id == "raven_ar9_site_inspection":
                return str(event.location or "")
        raise RuntimeError("site inspection event not found on calendar")

    def _minutes_open_items(self) -> list[str]:
        last: dict[str, str] = {}
        order: list[str] = []
        for line in self._cat(MINUTES_DOC_PATH).splitlines():
            stripped = line.strip()
            if stripped.startswith(MINUTES_OPEN_PREFIX):
                item = stripped[len(MINUTES_OPEN_PREFIX):].strip()
            elif stripped.startswith(MINUTES_CLOSED_PREFIX):
                item = stripped[len(MINUTES_CLOSED_PREFIX):].strip()
                if item:
                    last[item] = "CLOSED"
                    if item not in order:
                        order.append(item)
                continue
            else:
                continue
            if item:
                last[item] = "OPEN"
                if item not in order:
                    order.append(item)
        return [item for item in order if last[item] == "OPEN"]

    def step_read_anchor(self) -> None:
        matches = [
            event
            for event in self._calendar().events.values()
            if event.title == ANCHOR_TITLE
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one anchor event, found {len(matches)}")
        self.anchor_event_id = matches[0].event_id
        self.preserved_attendees = list(matches[0].attendees or [])

    def step_delete_anchor(self, event_id: str | None = None) -> None:
        self._calendar().delete_calendar_event(
            event_id or self.anchor_event_id or ANCHOR_EVENT_ID
        )

    def step_add_event(
        self,
        room: str | None = None,
        start: str | None = None,
        minutes: int | None = None,
        attendees: list[str] | None = None,
        title: str | None = None,
    ) -> None:
        start_stamp = start or self.discovered["new_meeting_time"]
        span = minutes if minutes is not None else self.discovered["new_duration_minutes"]
        end_stamp = to_stamp(to_epoch(start_stamp) + int(span) * 60)
        preserved = (
            attendees if attendees is not None else list(self.preserved_attendees)
        )
        if not preserved:
            raise RuntimeError("anchor attendees not captured; run read_anchor first")
        self.created_event_id = self._calendar().add_calendar_event(
            title=title or ANCHOR_TITLE,
            start_datetime=start_stamp,
            end_datetime=end_stamp,
            tag=ANCHOR_TAG,
            description="Rescheduled at client request.",
            location=room if room is not None else self.discovered["room_name"],
            attendees=list(preserved),
        )

    def step_delete_created_event(self) -> None:
        if self.created_event_id is None:
            raise RuntimeError("no in-episode calendar event to delete")
        self._calendar().delete_calendar_event(self.created_event_id)
        self.created_event_id = None

    def step_book_review(self, room: str | None = None) -> None:
        if self.chosen_room is None:
            raise RuntimeError("free room not derived; run derive_free_room first")
        self.booked_attendees = list(self.hardened.attendee_emails_after_a7)
        start_stamp = self.discovered["new_meeting_time"]
        end_stamp = self.hardened.meeting_end_after_a9
        self.created_event_id = self._calendar().add_calendar_event(
            title=ANCHOR_TITLE,
            start_datetime=start_stamp,
            end_datetime=end_stamp,
            tag=ANCHOR_TAG,
            description="Rescheduled at client request.",
            location=room if room is not None else self.chosen_room,
            attendees=list(self.booked_attendees),
        )

    def step_hold_room(self) -> None:
        if self.chosen_room is None:
            raise RuntimeError("free room not derived; run derive_free_room first")
        start_stamp = self.discovered["new_meeting_time"]
        end_stamp = self.hardened.meeting_end_after_a9
        self._calendar().add_calendar_event(
            title=f"{ROOM_HOLD_TITLE_PREFIX}{self.chosen_room}",
            start_datetime=start_stamp,
            end_datetime=end_stamp,
            tag=ROOM_HOLD_TAG,
            description=f"Agent hold on {self.chosen_room} for the rescheduled review.",
            location=self.chosen_room,
            attendees=[],
        )

    def step_travel_block(self) -> None:
        site = self._site_location()
        office = self.hardened.office_after_a5
        minutes = self._travel_minutes(site, office)
        start_epoch = self.discovered["new_meeting_time_epoch"]
        pickup_epoch = start_epoch - (minutes + 15) * 60
        self._calendar().add_calendar_event(
            title=f"{TRAVEL_BLOCK_TITLE_PREFIX}site to {office}",
            start_datetime=to_stamp(pickup_epoch),
            end_datetime=to_stamp(start_epoch),
            tag="travel",
            description=f"Travel from {site} to {office}.",
            location=site,
            attendees=[],
        )

    def step_rebook_ride(self) -> None:
        # Cancel-only: the replacement order is a separate step so its event_time is
        # strictly later than the cancel (grader requires min(cancel) < max(order)).
        if self.ride_ids:
            self.apps["CabApp"].user_cancel_ride()

    def step_order_rebooked(self) -> None:
        site = self._site_location()
        office = self.hardened.office_after_a5
        minutes = self._travel_minutes(site, office)
        start_epoch = self.discovered["new_meeting_time_epoch"]
        pickup_epoch = start_epoch - (minutes + 15) * 60
        ride = self.apps["CabApp"].order_ride(
            start_location=site,
            end_location=office,
            service_type=CAB_SERVICE_TYPE,
            ride_time=to_stamp(pickup_epoch),
        )
        self.ride_ids.append(ride.ride_id)

    def step_write_minutes_agenda(self, path: str | None = None) -> None:
        target = path or AGENDA_PATH
        open_items = self._minutes_open_items()
        items = list(self.discovered["agenda_items"]) + [
            item for item in open_items if item not in self.discovered["agenda_items"]
        ]
        body = "# Agenda\n\n" + "\n".join(f"- {item}" for item in items) + "\n"
        with self.apps["Files"].open(target, "w") as handle:
            handle.write(body)

    def step_procure(self) -> None:
        shop = self.apps["ShoppingApp"]
        headcount = 1 + len(self.booked_attendees)
        matches = shop.search_product("Catchment Review Delegate Pack")
        variant_id = None
        for product in matches:
            for item_id, item in (getattr(product, "variants", {}) or {}).items():
                if getattr(item, "available", False):
                    variant_id = item_id
                    break
            if variant_id:
                break
        if variant_id is None:
            raise RuntimeError("no available spec-conforming delegate pack variant")
        shop.add_to_cart(item_id=variant_id, quantity=headcount)
        shop.checkout()

    def step_notify_cover(self, channel: str = "Messages") -> None:
        self.apps["Emails"].send_email(
            recipients=["priya.nair@example.com"],
            subject="Cover for the catchment telemetry review",
            content=(
                f"Hi Priya, you are covering the catchment telemetry review now moved to "
                f"{self.discovered['new_meeting_time']} UTC in {self.chosen_room}. The "
                f"agenda pack is on its way to you."
            ),
        )

    def step_order_ride(
        self,
        end_location: str | None = None,
        pickup: str | None = None,
        lead_seconds: int | None = None,
    ) -> None:
        lead = CAB_LEAD_SECONDS if lead_seconds is None else int(lead_seconds)
        pickup_stamp = pickup or to_stamp(
            to_epoch(self.discovered["new_meeting_time"]) - lead
        )
        ride = self.apps["CabApp"].order_ride(
            start_location=CAB_START_LOCATION,
            end_location=end_location
            if end_location is not None
            else self.discovered["office_location"],
            service_type=CAB_SERVICE_TYPE,
            ride_time=pickup_stamp,
        )
        self.ride_ids.append(ride.ride_id)

    def step_cancel_ride(self) -> None:
        self.apps["CabApp"].user_cancel_ride()

    def step_notify(
        self,
        channel: str = "Messages",
        attendee_id: str | None = None,
        content: str | None = None,
    ) -> None:
        target = attendee_id or self.attendee_id
        if target is None:
            raise RuntimeError("attendee id not resolved; run lookup_attendee first")
        body = content or (
            f"Hi {self.discovered['attendee_identity']}, the program review has moved to "
            f"{self.discovered['new_meeting_time']} UTC in {self.discovered['room_name']}."
        )
        self.apps[channel].send_message(user_id=target, content=body)

    def step_write_agenda(self, path: str | None = None, items: list[str] | None = None) -> None:
        target = path or AGENDA_PATH
        realized = self.realized
        if items is None:
            body = agenda_document(realized)
        else:
            body = "# Agenda\n\n" + "\n".join(f"- {item}" for item in items) + "\n"
        with self.apps["Files"].open(target, "w") as handle:
            handle.write(body)

    def step_deliver_agenda(
        self,
        channel: str = "Messages",
        path: str | None = None,
        attendee_id: str | None = None,
        recipients: list[str] | None = None,
    ) -> None:
        target_path = path or AGENDA_PATH
        if channel == "Emails":
            raw = self.apps["Files"].cat(target_path)
            text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
            self.apps["Emails"].send_email(
                recipients=list(
                    recipients
                    if recipients is not None
                    else [self.discovered["attendee_email"]]
                ),
                subject="Agenda pack \u2014 catchment telemetry review",
                content=text,
            )
            return
        target = attendee_id or self.attendee_id
        if target is None:
            raise RuntimeError("attendee id not resolved; run lookup_attendee first")
        self.apps[channel].send_message(
            user_id=target,
            content="Agenda pack for the rescheduled review is attached.",
            attachment_path=target_path,
        )

    def step_confirm(self, content: str | None = None) -> None:
        room = self.chosen_room or self.discovered["room_name"]
        body = content or (
            f"Done. The client review is rescheduled to {self.discovered['new_meeting_time']} "
            f"UTC in {room}. A cab to the relocated office is booked, the attendee and cover "
            f"are notified, and the agenda pack has been delivered."
        )
        self.apps["AgentUserInterface"].send_message_to_user(content=body)

    def apply(self, actions: list[tuple[str, dict]]) -> None:
        for name, kwargs in actions:
            handler = getattr(self, f"step_{name}", None)
            if handler is None:
                raise RuntimeError(f"unknown oracle step {name!r}")
            if name not in UNTICKED_STEPS:
                self.clock.advance(STEP_SECONDS)
            handler(**kwargs)

    def report(self) -> dict:
        event_log = json.loads(self.env.event_log_json())
        entries = truth.past_events(event_log)
        # A legitimate no-op performs no in-episode app writes, so it dumps no app-state
        # and scores zero; only runs that actually mutate apps emit appstate.json. The
        # driver's own discovery/cutoff scaffolding emails (Emails.add_email) are excluded.
        did_mutate = any(
            (entry.get("action") or {}).get("operation_type") == "write"
            and not (
                (entry.get("action") or {}).get("app_name") == "Emails"
                and (entry.get("action") or {}).get("function_name") == "add_email"
            )
            for entry in entries
        )
        # The driver carries NO checker of its own: the shipped grader (tests/score.py) is the
        # single source of truth and `self_check` below runs it over the written artifact.
        return {
            "seed": self.realized.seed,
            "event_log": event_log,
            "clock": self.deterministic_clock.manifest(),
            "appstate": statedump.build_appstate(self.scenario.apps) if did_mutate else None,
            "sim_time_end": self.clock.now(),
        }


def ground_truth(seed: int | None = None) -> dict:
    return truth.expected(truth.realize(seed))


def oracle_actions(seed: int | None = None, channel: str = "Messages") -> list[tuple[str, dict]]:
    return [
        ("deliver_discovery", {}),
        ("read_discovery", {}),
        ("lookup_attendee", {}),
        ("resolve_role", {}),
        ("read_anchor", {}),
        ("fire_async", {"key": "A2"}),
        ("fire_async", {"key": "A3"}),
        ("fire_async", {"key": "A4"}),
        ("order_ride", {}),
        ("fire_async", {"key": "A5"}),
        ("fire_async", {"key": "A7"}),
        ("fire_async", {"key": "A6"}),
        ("fire_async", {"key": "A8"}),
        ("fire_async", {"key": "A9"}),
        ("delete_anchor", {}),
        ("derive_free_room", {}),
        ("add_second_attendee", {}),
        ("book_review", {}),
        ("hold_room", {}),
        ("travel_block", {}),
        ("page_role_holder", {}),
        ("rebook_ride", {}),
        ("order_rebooked", {}),
        ("write_minutes_agenda", {}),
        ("notify", {"channel": channel}),
        ("notify_cover", {"channel": channel}),
        ("deliver_agenda", {"channel": channel}),
        ("procure", {}),
        ("confirm", {}),
        ("cutoff", {}),
    ]


def alternate_messages(seed: int | None = None) -> list[tuple[str, dict]]:
    return oracle_actions(seed, channel="Messages")


def alternate_chats(seed: int | None = None) -> list[tuple[str, dict]]:
    return oracle_actions(seed, channel="Chats")


def alternate_self_correct(seed: int | None = None) -> list[tuple[str, dict]]:
    # The full hardened oracle with a REVERSIBLE detour: book the review in a wrong (occupied)
    # room, notice, delete that booking, re-derive the free room, then continue. Only state
    # that can be undone is detoured; a message to a wrong entity cannot be unsent and is a
    # graded fault by design, so no such detour belongs in a passing alternate.
    detour = [
        ("force_occupied_room", {}),
        ("book_review", {}),
        ("delete_created_event", {}),
        ("derive_free_room", {}),
    ]
    out: list[tuple[str, dict]] = []
    for step in oracle_actions(seed):
        out.append(step)
        if step[0] == "derive_free_room":
            out.extend(detour)
    return out


def control_noop(seed: int | None = None) -> list[tuple[str, dict]]:
    return [("deliver_discovery", {}), ("read_discovery", {}), ("cutoff", {})]


def control_baseline_only(seed: int | None = None) -> list[tuple[str, dict]]:
    return [
        ("deliver_discovery", {}),
        ("read_discovery", {}),
        ("lookup_attendee", {}),
        ("read_anchor", {}),
        ("confirm", {"content": "Nothing to do, the existing calendar already covers it."}),
        ("cutoff", {}),
    ]


def control_wrong_room(seed: int | None = None) -> list[tuple[str, dict]]:
    # Hardened oracle, but the derived free room is swapped for an occupied one before every
    # room-bearing write (book_review / hold_room), so the final booking is in a wrong room.
    out: list[tuple[str, dict]] = []
    for step in oracle_actions(seed):
        out.append(step)
        if step[0] == "derive_free_room":
            out.append(("force_occupied_room", {}))
    return out


def control_wrong_attendee(seed: int | None = None) -> list[tuple[str, dict]]:
    realized = truth.realize(seed)
    wrong_attendee = next(
        contact_id
        for _, contact_id, _ in ATTENDEE_POOL
        if contact_id != realized.attendee_contact_id
    )
    return [
        (
            name,
            dict(kwargs, attendee_id=wrong_attendee)
            if name in ("notify", "deliver_agenda")
            else kwargs,
        )
        for name, kwargs in oracle_actions(seed)
    ]


def control_no_delete(seed: int | None = None) -> list[tuple[str, dict]]:
    return [step for step in oracle_actions(seed) if step[0] != "delete_anchor"]


def control_late(seed: int | None = None) -> list[tuple[str, dict]]:
    # Hardened oracle whose state-writing tail lands AFTER the deadline. The async arcs fire at
    # fixed sim offsets before the deadline, so the cutoff is placed after the last fire_async
    # (sim time only moves forward); everything from delete_anchor onward is then late.
    realized = truth.realize(seed)
    steps = [step for step in oracle_actions(seed) if step[0] != "cutoff"]
    last_async = max(i for i, step in enumerate(steps) if step[0] == "fire_async")
    head, tail = steps[: last_async + 1], steps[last_async + 1 :]
    return head + [("cutoff", {}), ("advance", {"to": realized.stated_deadline_epoch + 60})] + tail


ALTERNATES = {
    "alt1_messages": alternate_messages,
    "alt2_self_correct": alternate_self_correct,
    "alt3_chats": alternate_chats,
}

CONTROLS = {
    "noop": control_noop,
    "baseline_only": control_baseline_only,
    "wrong_room": control_wrong_room,
    "wrong_attendee": control_wrong_attendee,
    "no_delete": control_no_delete,
    "late": control_late,
}

MODES = {"oracle": oracle_actions, **ALTERNATES, **CONTROLS}


def run_trajectory(actions: list[tuple[str, dict]], seed: int | None = None) -> dict:
    run = OracleRun(seed)
    run.apply(actions)
    return run.report()


def run_mode(mode: str, seed: int | None = None) -> dict:
    if mode not in MODES:
        raise RuntimeError(f"unknown mode {mode!r}; known: {sorted(MODES)}")
    payload = run_trajectory(MODES[mode](seed), seed)
    payload["mode"] = mode
    return payload


def _durable_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _write(target: Path, payload: dict) -> Path:
    if target.is_dir() or target.suffix == "":
        target = target / "eventlog.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    artifact = dict(payload["event_log"])
    if payload.get("clock") is not None:
        artifact["clock"] = payload["clock"]
    _durable_write(target, json.dumps(artifact))
    if payload.get("appstate") is not None:
        _durable_write(
            target.with_name("appstate.json"),
            json.dumps(payload["appstate"], default=str),
        )
    return target


def expected_full_success(mode: str) -> bool:
    return mode == "oracle" or mode in ALTERNATES


def replay_to_authority() -> dict:
    """Run the reference oracle in-process and write the authoritative artifacts.

    Writes the same event log + top-level clock manifest + app-state the delivered
    server path produces, to RAVEN_EVENTLOG_OUT / RAVEN_APPSTATE_OUT (the oracle-only
    /authority volume the collect hook reads). This is the identical OracleRun that
    scores 1.0 author-side; only the output location differs.
    """
    import os

    eventlog = Path(os.environ.get("RAVEN_EVENTLOG_OUT", str(DEFAULT_EVENTLOG)))
    appstate = os.environ.get("RAVEN_APPSTATE_OUT")
    payload = run_mode("oracle")
    _write(eventlog, payload)
    if appstate and payload.get("appstate") is not None:
        _durable_write(Path(appstate), json.dumps(payload["appstate"], default=str))
    elif payload.get("appstate") is not None:
        _durable_write(
            eventlog.with_name("appstate.json"),
            json.dumps(payload["appstate"], default=str),
        )
    return payload


def _serve_until_terminated(host: str = "0.0.0.0", port: int = 8000) -> None:
    import os
    import signal
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, int(os.environ.get("FASTMCP_PORT", port))))
    sock.listen(16)

    def _halt(signum: int, frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _halt)
    signal.signal(signal.SIGINT, _halt)
    while True:
        try:
            conn, _ = sock.accept()
            conn.close()
        except (OSError, SystemExit):
            break


def main(argv: list[str] | None = None) -> int:
    payload = replay_to_authority()
    print(f"oracle replay: seed={payload['seed']} wrote authority artifacts", flush=True)
    _serve_until_terminated()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
