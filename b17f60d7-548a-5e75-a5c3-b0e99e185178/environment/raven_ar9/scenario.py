from __future__ import annotations

import os

from are.simulation.apps.calendar import CalendarEvent
from are.simulation.apps.email_client import Email, EmailFolderName
from are.simulation.data_handler.importer import JsonScenarioImporter
from are.simulation.environment import AbstractEnvironment
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.types import (
    ConditionCheckEvent,
    Event,
    EventRegisterer,
    EventType,
)

from raven_ar9.realize import (
    A3_DEADLINE_SHIFT_SECONDS,
    A4_COVER_EMAIL,
    A7_ATTENDEE_EMAIL,
    AGENDA_PATH,
    ANCHOR_DESCRIPTION,
    ANCHOR_END_EPOCH,
    ANCHOR_EVENT_ID,
    ANCHOR_LOCATION,
    ANCHOR_START_EPOCH,
    ANCHOR_TAG,
    ANCHOR_TITLE,
    ASYNC_EVENT_IDS,
    ASYNC_EVENT_OFFSETS,
    ASYNC_GATE_IDS,
    ASYNC_GATE_TICK_SECONDS,
    BASELINE_RIDE_COUNT,
    CLIENT_EMAIL_EVENT_ID,
    CLIENT_NAME,
    CLIENT_SENDER,
    CLIENT_SUBJECT,
    CUTOFF_EVENT_ID,
    DURATION_SECONDS,
    FACILITIES_DIR,
    MINUTES_CLOSED_PREFIX,
    MINUTES_DIR,
    MINUTES_DOC_PATH,
    MINUTES_OPEN_PREFIX,
    MINUTES_THREAD_EMAIL_ID,
    MINUTES_THREAD_OFFSET_SECONDS,
    MINUTES_THREAD_SENDER,
    MINUTES_THREAD_SUBJECT,
    PACK_ITEM_ID,
    PROCUREMENT_DOC_PATH,
    ROOM_HOLD_OWNER,
    ROOM_HOLD_TAG,
    ROOM_HOLD_TITLE_PREFIX,
    ROOM_POOL,
    ROOMS_DOC_PATH,
    SCENARIO_ID,
    SITE_INSPECTION_DESCRIPTION,
    SITE_INSPECTION_EVENT_ID,
    SITE_INSPECTION_TAG,
    SITE_INSPECTION_TITLE,
    START_TIME,
    T_EMAIL,
    TIME_INCREMENT_SECONDS,
    TRAVEL_DOC_PATH,
    UNIVERSE_APP_COUNT,
    USER_EMAIL,
    HardenedState,
    RealizedState,
    client_email_body_hardened,
    derive,
    derive_hardened,
    minutes_document,
    minutes_thread_body,
    procurement_document,
    rooms_document,
    travel_document,
)

DEFAULT_SEED = 7742
SEED_ENV_VAR = "RAVEN_EPISODE_SEED"
UNIVERSE_ENV_VAR = "RAVEN_UNIVERSE_PATH"
DEFAULT_UNIVERSE_PATH = "/task/universe_0.json"

CUTOFF_SUBJECT = "Confirmation window closed"
CUTOFF_BODY = (
    f"Mara,\n\nThe confirmation window I gave you has now closed.\n\n{CLIENT_NAME}\n"
    f"Catchment Partners\n"
)

A2_SUBJECT = "Room taken for your window"
A3_SUBJECT = "Confirmation window pulled forward"
A4_SUBJECT = "Attendee swap for the review"
A5_SUBJECT = "We have moved offices for this session"
A6_SUBJECT = "Addendum to the 3 Oct minutes"
A7_SUBJECT = "One more attendee for the review"
A8_SUBJECT = "Delegate pack unavailable"
A9_SUBJECT = "Shorter slot for the review"


def episode_seed() -> int:
    raw = os.environ.get(SEED_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_SEED
    return int(raw.strip())


def _realized_for_run() -> RealizedState:
    injected = getattr(RavenAR9, "_injected_realized", None)
    if isinstance(injected, RealizedState):
        return injected
    return derive(episode_seed())


def _anchor_calendar_event(realized: RealizedState) -> CalendarEvent:
    return CalendarEvent(
        event_id=ANCHOR_EVENT_ID,
        title=ANCHOR_TITLE,
        start_datetime=ANCHOR_START_EPOCH,
        end_datetime=ANCHOR_END_EPOCH,
        tag=ANCHOR_TAG,
        description=ANCHOR_DESCRIPTION,
        location=ANCHOR_LOCATION,
        attendees=list(realized.anchor_attendees),
    )


def _seed_anchor_event(calendar, realized: RealizedState) -> None:
    if ANCHOR_EVENT_ID in calendar.events:
        raise RuntimeError(f"anchor event id {ANCHOR_EVENT_ID} already present in universe")
    collisions = [e.event_id for e in calendar.events.values() if e.title == ANCHOR_TITLE]
    if collisions:
        raise RuntimeError(f"anchor title collides with universe events {collisions}")
    event = _anchor_calendar_event(realized)
    calendar.events[event.event_id] = event


def _bind_messaging_filesystem(apps_by_name: dict) -> None:
    # MessagingAppV2._create_message resolves attachment_path through internal_fs; the ARE
    # universe import leaves it None, which makes every sandbox-relative attachment path
    # unresolvable. Binding it to the Files app is what makes attachment delivery reachable.
    files = apps_by_name["Files"]
    for name in ("Messages", "Chats"):
        apps_by_name[name].internal_fs = files


def _seed_site_inspection(calendar, hardened: HardenedState) -> None:
    if SITE_INSPECTION_EVENT_ID in calendar.events:
        raise RuntimeError(f"site inspection id {SITE_INSPECTION_EVENT_ID} already present")
    collisions = [
        e.event_id
        for e in calendar.events.values()
        if e.title == SITE_INSPECTION_TITLE
    ]
    if collisions:
        raise RuntimeError(f"site inspection title collides with {collisions}")
    calendar.events[SITE_INSPECTION_EVENT_ID] = CalendarEvent(
        event_id=SITE_INSPECTION_EVENT_ID,
        title=SITE_INSPECTION_TITLE,
        start_datetime=hardened.site_start_epoch,
        end_datetime=hardened.site_end_epoch,
        tag=SITE_INSPECTION_TAG,
        description=SITE_INSPECTION_DESCRIPTION,
        location=hardened.site_location,
        attendees=[USER_EMAIL],
    )


def _seed_room_holds(calendar, hardened: HardenedState) -> None:
    for event_id, room, start_epoch, end_epoch in hardened.room_holds_baseline:
        if event_id in calendar.events:
            raise RuntimeError(f"room hold id {event_id} already present in universe")
        calendar.events[event_id] = CalendarEvent(
            event_id=event_id,
            title=f"{ROOM_HOLD_TITLE_PREFIX}{room}",
            start_datetime=start_epoch,
            end_datetime=end_epoch,
            tag=ROOM_HOLD_TAG,
            description=f"Standing facilities hold on {room}.",
            location=room,
            attendees=[ROOM_HOLD_OWNER],
        )


def _seed_minutes_thread(emails, hardened: HardenedState) -> None:
    with EventRegisterer.disable():
        emails.add_email(
            Email(
                email_id=MINUTES_THREAD_EMAIL_ID,
                sender=MINUTES_THREAD_SENDER,
                recipients=[USER_EMAIL],
                subject=MINUTES_THREAD_SUBJECT,
                content=minutes_thread_body(),
                timestamp=START_TIME + MINUTES_THREAD_OFFSET_SECONDS,
            ),
            folder_name=EmailFolderName.INBOX,
        )


def _write_reference_documents(files, hardened: HardenedState) -> None:
    documents = {
        ROOMS_DOC_PATH: rooms_document(),
        PROCUREMENT_DOC_PATH: procurement_document(),
        TRAVEL_DOC_PATH: travel_document(),
        MINUTES_DOC_PATH: minutes_document(
            hardened.minutes_open_baseline, hardened.minutes_closed_baseline
        ),
    }
    with EventRegisterer.disable():
        for directory in (FACILITIES_DIR, MINUTES_DIR):
            files.makedirs(directory, exist_ok=True)
        for path, body in documents.items():
            with files.open(path, "w") as handle:
                handle.write(body)


def client_email(realized: RealizedState) -> Email:
    return Email(
        sender=CLIENT_SENDER,
        recipients=[USER_EMAIL],
        subject=CLIENT_SUBJECT,
        content=client_email_body_hardened(realized),
        timestamp=START_TIME + T_EMAIL,
    )


def cutoff_marker_email() -> Email:
    return Email(
        sender=CLIENT_SENDER,
        recipients=[USER_EMAIL],
        subject=CUTOFF_SUBJECT,
        content=CUTOFF_BODY,
    )


def _notice(subject: str, body: str, offset: float) -> Email:
    return Email(
        sender=CLIENT_SENDER,
        recipients=[USER_EMAIL],
        subject=subject,
        content=f"Mara,\n\n{body}\n\n{CLIENT_NAME}\nCatchment Partners\n",
        timestamp=START_TIME + offset,
    )


def _canonical_room_locations(calendar) -> set[str]:
    return {
        event.location
        for event in calendar.events.values()
        if event.tag != ROOM_HOLD_TAG and event.location in ROOM_POOL
    }


@register_scenario(SCENARIO_ID)
class RavenAR9(Scenario):
    start_time: float | None = START_TIME
    duration: float | None = DURATION_SECONDS
    time_increment_in_seconds: int = TIME_INCREMENT_SECONDS

    def init_and_populate_apps(self, *args, **kwargs) -> None:
        universe = os.environ.get(UNIVERSE_ENV_VAR, DEFAULT_UNIVERSE_PATH)
        with open(universe, encoding="utf-8") as handle:
            payload = handle.read()
        imported, _, _ = JsonScenarioImporter().import_from_json(payload, apps_to_skip=[])
        imported.initialize()
        universe_apps = list(imported.apps or [])
        if len(universe_apps) != UNIVERSE_APP_COUNT:
            raise RuntimeError(
                f"universe {universe} yielded {len(universe_apps)} apps, "
                f"expected {UNIVERSE_APP_COUNT}"
            )
        empty = [app.name for app in universe_apps if not app.get_state()]
        if empty:
            raise RuntimeError(f"universe apps imported with empty state: {empty}")
        apps_by_name = {app.name: app for app in universe_apps}
        self.realized = _realized_for_run()
        self.hardened = derive_hardened(self.realized)
        self.apps = universe_apps
        _bind_messaging_filesystem(apps_by_name)
        _seed_anchor_event(apps_by_name["Calendar"], self.realized)
        _seed_site_inspection(apps_by_name["Calendar"], self.hardened)
        _seed_room_holds(apps_by_name["Calendar"], self.hardened)
        _seed_minutes_thread(apps_by_name["Emails"], self.hardened)
        _write_reference_documents(apps_by_name["Files"], self.hardened)

    def build_events_flow(self) -> None:
        emails = self.get_app("Emails")
        calendar = self.get_app("Calendar")
        files = self.get_app("Files")
        shopping = self.get_app("ShoppingApp")
        cab = self.get_app("CabApp")
        realized = self.realized
        hardened = self.hardened

        def env_email(subject: str, body: str, key: str) -> None:
            with EventRegisterer.disable():
                emails.add_email(
                    _notice(subject, body, ASYNC_EVENT_OFFSETS[key]),
                    folder_name=EmailFolderName.INBOX,
                )

        def notice_already_sent(subject: str) -> bool:
            folder = emails.folders[EmailFolderName.INBOX]
            return any(mail.subject == subject for mail in folder.emails)

        def apply_a2_room_taken() -> None:
            if notice_already_sent(A2_SUBJECT):
                return
            released = None
            for event_id, room, _start, _end in hardened.room_holds_baseline:
                if room == hardened.free_room_after_a2:
                    released = event_id
            if released is not None and released in calendar.events:
                del calendar.events[released]
            for event_id, room, start_epoch, end_epoch in hardened.room_holds_after_a2:
                if event_id in calendar.events:
                    continue
                calendar.events[event_id] = CalendarEvent(
                    event_id=event_id,
                    title=f"{ROOM_HOLD_TITLE_PREFIX}{room}",
                    start_datetime=start_epoch,
                    end_datetime=end_epoch,
                    tag=ROOM_HOLD_TAG,
                    description=f"Standing facilities hold on {room}.",
                    location=room,
                    attendees=[ROOM_HOLD_OWNER],
                )
            env_email(
                A2_SUBJECT,
                f"Facilities have taken {hardened.free_room_baseline} for your window and "
                f"released another room. Re-derive the free canonical room from "
                f"{ROOMS_DOC_PATH} against the calendar as it stands now.",
                "A2",
            )

        def apply_a3_deadline_pulled() -> None:
            if notice_already_sent(A3_SUBJECT):
                return
            env_email(
                A3_SUBJECT,
                f"The confirmation window moves {abs(A3_DEADLINE_SHIFT_SECONDS) // 60} "
                f"minutes earlier. New confirm-by is {hardened.deadline_after_a3} UTC.",
                "A3",
            )

        def apply_a4_attendee_on_leave() -> None:
            if notice_already_sent(A4_SUBJECT):
                return
            env_email(
                A4_SUBJECT,
                f"{realized.attendee_identity} went on leave this morning. "
                f"{A4_COVER_EMAIL} covers the session, so "
                f"{realized.attendee_email} should come off the booking. The agenda pack "
                f"goes to the covering attendee.",
                "A4",
            )

        def apply_a5_office_relocated() -> None:
            if notice_already_sent(A5_SUBJECT):
                return
            env_email(
                A5_SUBJECT,
                f"We have moved this session to {hardened.office_after_a5}. Any ride you "
                f"already booked is for the wrong destination; cancel it and rebook from "
                f"the inspection site, and re-derive the pickup from {TRAVEL_DOC_PATH}.",
                "A5",
            )

        def apply_a6_minutes_addendum() -> None:
            if notice_already_sent(A6_SUBJECT):
                return
            with EventRegisterer.disable():
                with files.open(MINUTES_DOC_PATH, "w") as handle:
                    handle.write(
                        minutes_document(
                            hardened.minutes_open_baseline,
                            hardened.minutes_closed_baseline,
                            addendum=(
                                (MINUTES_OPEN_PREFIX, hardened.minutes_a6_opened),
                                (MINUTES_CLOSED_PREFIX, hardened.minutes_a6_closed),
                            ),
                        )
                    )
            env_email(
                A6_SUBJECT,
                f"An addendum has been appended to {MINUTES_DOC_PATH}. One item opens and "
                f"one item closes. The addendum overrides the register above it.",
                "A6",
            )

        def apply_a7_second_attendee() -> None:
            if notice_already_sent(A7_SUBJECT):
                return
            env_email(
                A7_SUBJECT,
                f"Please add {A7_ATTENDEE_EMAIL} to the booking. He is new and is not in "
                f"either address book yet, so you will have to add him before you can "
                f"message him.",
                "A7",
            )

        def apply_a8_pack_out_of_stock() -> None:
            if notice_already_sent(A8_SUBJECT):
                return
            with EventRegisterer.disable():
                shopping.update_item(item_id=PACK_ITEM_ID, new_availability=False)
            env_email(
                A8_SUBJECT,
                f"The supplier has pulled the standard delegate pack. Follow the "
                f"substitution rule in {PROCUREMENT_DOC_PATH}.",
                "A8",
            )

        def apply_a9_duration_cut() -> None:
            if notice_already_sent(A9_SUBJECT):
                return
            env_email(
                A9_SUBJECT,
                f"We only need {hardened.duration_after_a9} minutes now, not "
                f"{realized.new_duration_minutes}. The start time is unchanged, so the "
                f"session now ends {hardened.meeting_end_after_a9} UTC.",
                "A9",
            )

        def gate_a2_room_chosen(env: AbstractEnvironment) -> bool:
            return bool(_canonical_room_locations(calendar))

        def gate_a5_ride_ordered(env: AbstractEnvironment) -> bool:
            return len(cab.ride_history) > BASELINE_RIDE_COUNT

        def gate_a6_agenda_written(env: AbstractEnvironment) -> bool:
            with EventRegisterer.disable():
                return bool(files.exists(AGENDA_PATH))

        def gate_a8_pack_procured(env: AbstractEnvironment) -> bool:
            return bool(shopping.cart) or bool(shopping.orders)

        discovery = (
            Event.from_function(
                emails.add_email,
                event_type=EventType.ENV,
                email=client_email(realized),
                folder_name=EmailFolderName.INBOX,
            )
            .with_id(CLIENT_EMAIL_EVENT_ID)
            .at_absolute_time(START_TIME + T_EMAIL)
        )
        cutoff = (
            Event.from_function(
                emails.add_email,
                event_type=EventType.ENV,
                email=cutoff_marker_email(),
                folder_name=EmailFolderName.INBOX,
            )
            .with_id(CUTOFF_EVENT_ID)
            .at_absolute_time(realized.stated_deadline_epoch)
        )

        mutators = {
            "A2": apply_a2_room_taken,
            "A3": apply_a3_deadline_pulled,
            "A4": apply_a4_attendee_on_leave,
            "A5": apply_a5_office_relocated,
            "A6": apply_a6_minutes_addendum,
            "A7": apply_a7_second_attendee,
            "A8": apply_a8_pack_out_of_stock,
            "A9": apply_a9_duration_cut,
        }
        gates = {
            "A2": gate_a2_room_chosen,
            "A5": gate_a5_ride_ordered,
            "A6": gate_a6_agenda_written,
            "A8": gate_a8_pack_procured,
        }

        flow = [discovery, cutoff]
        for key, mutator in mutators.items():
            backstop = (
                Event.from_function(mutator, event_type=EventType.ENV)
                .with_id(ASYNC_EVENT_IDS[key])
                .at_absolute_time(START_TIME + ASYNC_EVENT_OFFSETS[key])
            )
            flow.append(backstop)
            if key not in gates:
                continue
            gate = ConditionCheckEvent.from_condition(
                gates[key], every_tick=ASYNC_GATE_TICK_SECONDS
            )
            gate = gate.with_id(ASYNC_GATE_IDS[key]).at_absolute_time(START_TIME + T_EMAIL)
            triggered = Event.from_function(
                mutator, event_type=EventType.ENV
            ).with_id(f"{ASYNC_EVENT_IDS[key]}_triggered")
            triggered.depends_on([gate])
            flow.extend([gate, triggered])
        self.events = flow

    def validate(self, env: AbstractEnvironment) -> ScenarioValidationResult:
        try:
            realized = self.realized
            hardened = self.hardened
            calendar = self.get_app("Calendar")
            rescheduled = [
                event
                for event in calendar.events.values()
                if event.event_id != ANCHOR_EVENT_ID
                and event.tag != ROOM_HOLD_TAG
                and event.start_datetime == realized.new_meeting_time_epoch
                and event.end_datetime == hardened.meeting_end_epoch_after_a9
                and event.location == hardened.free_room_after_a2
            ]
            anchor_removed = ANCHOR_EVENT_ID not in calendar.events
            return ScenarioValidationResult(success=bool(rescheduled) and anchor_removed)
        except Exception as exc:
            return ScenarioValidationResult(success=False, exception=exc)
