from __future__ import annotations

import base64

from raven_ar9.realize import (
    AGENDA_PATH,
    ANCHOR_EVENT_ID,
    BASELINE_RIDE_COUNT,
    CAB_SERVICE_TYPE,
    START_TIME,
    RealizedState,
    derive,
    to_epoch,
)

ORACLE_SEED = 7742

OBLIGATIONS = (
    "O1_RESCHEDULE",
    "O2_ROOM",
    "O3_ATTENDEES_PRESERVED",
    "O4_ANCHOR_REMOVED",
    "O5_CAB_BOOKED",
    "O6_NOTIFY_ATTENDEE",
    "O7_AGENDA_DOC",
    "O8_AGENDA_DELIVERED",
    "O9_USER_CONFIRMATION",
)

CALENDAR_WRITE = ("Calendar", "add_calendar_event")
CALENDAR_DELETE = ("Calendar", "delete_calendar_event")
CAB_WRITE = ("CabApp", "order_ride")
MESSAGING_WRITE = (("Messages", "send_message"), ("Chats", "send_message"))
EMAIL_WRITE = ("Emails", "send_email")
FILE_WRITE = ("Files", "open")
USER_WRITE = ("AgentUserInterface", "send_message_to_user")


def realize(seed: int | None = None) -> RealizedState:
    return derive(ORACLE_SEED if seed is None else int(seed))


def expected(realized: RealizedState) -> dict:
    return {
        "seed": realized.seed,
        "new_meeting_time": realized.new_meeting_time,
        "new_meeting_time_epoch": realized.new_meeting_time_epoch,
        "new_meeting_end": realized.new_meeting_end,
        "new_meeting_end_epoch": realized.new_meeting_end_epoch,
        "new_duration_minutes": realized.new_duration_minutes,
        "stated_deadline": realized.stated_deadline,
        "stated_deadline_epoch": realized.stated_deadline_epoch,
        "attendee_identity": realized.attendee_identity,
        "attendee_contact_id": realized.attendee_contact_id,
        "attendee_email": realized.attendee_email,
        "office_location": realized.office_location,
        "room_name": realized.room_name,
        "agenda_items": list(realized.agenda_items),
        "cab_pickup_time": realized.cab_pickup_time,
        "cab_pickup_epoch": realized.cab_pickup_epoch,
        "anchor_attendees": list(realized.anchor_attendees),
        "anchor_event_id": ANCHOR_EVENT_ID,
        "agenda_path": AGENDA_PATH,
        "cab_service_type": CAB_SERVICE_TYPE,
    }


def _contains_all(haystack: str, needles) -> bool:
    low = haystack.lower()
    return all(str(n).lower() in low for n in needles)


def _decode_attachment(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        raw = raw.encode()
    try:
        return base64.b64decode(raw).decode("utf-8", "replace")
    except Exception:
        return raw.decode("utf-8", "replace")


def _in_episode_messages(app):
    found = []
    for conversation in app.conversations.values():
        for message in conversation.messages:
            if message.timestamp >= START_TIME and message.sender_id == app.current_user_id:
                found.append((conversation, message))
    found.sort(key=lambda pair: pair[1].timestamp)
    return found


def _in_episode_rides(app):
    return list(app.ride_history[BASELINE_RIDE_COUNT:])


def _sent_emails(app):
    from are.simulation.apps.email_client import EmailFolderName

    folder = app.folders[EmailFolderName.SENT]
    return sorted(
        [mail for mail in folder.emails if mail.timestamp >= START_TIME],
        key=lambda mail: mail.timestamp,
    )


def _baseline_calendar_ids(app, baseline: set[str] | None) -> set[str]:
    if baseline is not None:
        return baseline
    return set()


def evaluate_state(
    apps_by_name: dict,
    realized: RealizedState,
    baseline_calendar_ids: set[str] | None = None,
) -> dict:
    calendar = apps_by_name["Calendar"]
    cab = apps_by_name["CabApp"]
    files = apps_by_name["Files"]
    emails = apps_by_name["Emails"]
    aui = apps_by_name["AgentUserInterface"]
    baseline = _baseline_calendar_ids(calendar, baseline_calendar_ids)

    fresh = [
        event
        for event in calendar.events.values()
        if event.event_id not in baseline and event.event_id != ANCHOR_EVENT_ID
    ]
    timed = [
        event
        for event in fresh
        if event.start_datetime == realized.new_meeting_time_epoch
        and event.end_datetime == realized.new_meeting_end_epoch
    ]
    roomed = [event for event in timed if event.location == realized.room_name]
    attended = [
        event
        for event in timed
        if set(realized.anchor_attendees).issubset(set(event.attendees or []))
    ]

    rides = _in_episode_rides(cab)
    last_ride = rides[-1] if rides else None
    cab_ok = bool(
        last_ride is not None
        and last_ride.status == "BOOKED"
        and last_ride.end_location == realized.office_location
        and float(last_ride.time_stamp) == realized.cab_pickup_epoch
    )

    notify_ok = False
    deliver_ok = False
    for app_name in ("Messages", "Chats"):
        app = apps_by_name[app_name]
        for conversation, message in _in_episode_messages(app):
            if realized.attendee_contact_id not in (conversation.participant_ids or []):
                continue
            body = message.content or ""
            if realized.new_meeting_time in body:
                notify_ok = True
            attachment = _decode_attachment(getattr(message, "attachment", None))
            if _contains_all(body, realized.agenda_items) or _contains_all(
                attachment, realized.agenda_items
            ):
                deliver_ok = True

    for mail in _sent_emails(emails):
        if realized.attendee_email not in (mail.recipients or []):
            continue
        if _contains_all(mail.content or "", realized.agenda_items):
            deliver_ok = True
        for raw in (mail.attachments or {}).values():
            if _contains_all(_decode_attachment(raw), realized.agenda_items):
                deliver_ok = True

    doc_ok = False
    if files.exists(AGENDA_PATH):
        raw = files.cat(AGENDA_PATH)
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        doc_ok = _contains_all(text, realized.agenda_items)

    user_messages = [
        entry
        for entry in aui.get_state().get("messages", [])
        if str(entry.get("sender", "")).endswith("AGENT")
    ]
    confirm_ok = any(
        _contains_all(entry.get("content", ""), [realized.new_meeting_time, realized.room_name])
        for entry in user_messages
    )

    return {
        "O1_RESCHEDULE": bool(timed),
        "O2_ROOM": bool(roomed),
        "O3_ATTENDEES_PRESERVED": bool(attended),
        "O4_ANCHOR_REMOVED": ANCHOR_EVENT_ID not in calendar.events,
        "O5_CAB_BOOKED": cab_ok,
        "O6_NOTIFY_ATTENDEE": notify_ok,
        "O7_AGENDA_DOC": doc_ok,
        "O8_AGENDA_DELIVERED": deliver_ok,
        "O9_USER_CONFIRMATION": confirm_ok,
    }


def past_events(event_log) -> list:
    if isinstance(event_log, list):
        return event_log
    inner = event_log.get("event_log", event_log)
    return list(inner.get("past_events") or [])


def log_entries(entries: list, app_name: str, function_name: str) -> list:
    picked = [
        entry
        for entry in entries
        if (entry.get("action") or {}).get("app_name") == app_name
        and (entry.get("action") or {}).get("function_name") == function_name
    ]
    picked.sort(key=lambda entry: float(entry.get("event_time") or 0.0))
    return picked


def agent_writes(entries: list, app_name: str, function_name: str) -> list:
    return [
        entry
        for entry in log_entries(entries, app_name, function_name)
        if entry.get("event_type") == "AGENT"
        and (entry.get("action") or {}).get("operation_type") == "write"
    ]


def cutoff_from_log(entries: list, realized: RealizedState) -> float:
    from raven_ar9.realize import CUTOFF_EVENT_ID

    for entry in entries:
        if str(entry.get("event_id", "")).startswith(CUTOFF_EVENT_ID):
            return float(entry.get("event_time"))
    return realized.stated_deadline_epoch


def last_tagged(entries: list, app_name: str, function_name: str, predicate) -> dict | None:
    tagged = [
        entry
        for entry in agent_writes(entries, app_name, function_name)
        if predicate((entry.get("action") or {}).get("args") or {})
    ]
    return tagged[-1] if tagged else None


def evaluate_log(event_log, realized: RealizedState) -> dict:
    entries = past_events(event_log)
    cutoff = cutoff_from_log(entries, realized)

    def is_target_event(args):
        start = args.get("start_datetime")
        if not start:
            return False
        return (
            to_epoch(str(start)) == realized.new_meeting_time_epoch
            and args.get("location") == realized.room_name
        )

    def is_target_ride(args):
        return args.get("end_location") == realized.office_location

    calendar_writes = agent_writes(entries, *CALENDAR_WRITE)
    cab_writes = agent_writes(entries, *CAB_WRITE)
    last_calendar = calendar_writes[-1] if calendar_writes else None
    last_cab = cab_writes[-1] if cab_writes else None
    target_event = last_tagged(entries, *CALENDAR_WRITE, is_target_event)
    target_ride = last_tagged(entries, *CAB_WRITE, is_target_ride)
    confirmations = agent_writes(entries, *USER_WRITE)
    last_confirmation = confirmations[-1] if confirmations else None

    return {
        "cutoff_epoch": cutoff,
        "calendar_write_count": len(calendar_writes),
        "cab_write_count": len(cab_writes),
        "last_calendar_write_before_cutoff": bool(
            last_calendar is not None and float(last_calendar["event_time"]) < cutoff
        ),
        "last_cab_write_before_cutoff": bool(
            last_cab is not None and float(last_cab["event_time"]) < cutoff
        ),
        "calendar_target_write_present": target_event is not None,
        "calendar_target_write_time": (
            float(target_event["event_time"]) if target_event else None
        ),
        "calendar_target_write_before_cutoff": bool(
            target_event is not None and float(target_event["event_time"]) < cutoff
        ),
        "cab_target_write_present": target_ride is not None,
        "cab_target_write_before_cutoff": bool(
            target_ride is not None and float(target_ride["event_time"]) < cutoff
        ),
        "confirmation_before_cutoff": bool(
            last_confirmation is not None
            and float(last_confirmation["event_time"]) < cutoff
        ),
        "all_target_writes_before_cutoff": bool(
            target_event is not None
            and target_ride is not None
            and last_confirmation is not None
            and max(
                float(target_event["event_time"]),
                float(target_ride["event_time"]),
                float(last_confirmation["event_time"]),
            )
            < cutoff
        ),
        "any_write_after_cutoff": any(
            float(entry.get("event_time") or 0.0) >= cutoff
            for entry in entries
            if entry.get("event_type") == "AGENT"
            and (entry.get("action") or {}).get("operation_type") == "write"
        ),
    }
