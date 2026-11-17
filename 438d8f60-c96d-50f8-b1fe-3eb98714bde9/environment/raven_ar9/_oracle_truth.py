from __future__ import annotations

from raven_ar9.realize import (
    HOTEL_LOCATION,
    ROUTE_Q_ITEM_ID,
    START_TIME,
    RealizedState,
    derive,
)

ORACLE_SEED = 7742


def realize(seed: int | None = None) -> RealizedState:
    return derive(ORACLE_SEED if seed is None else int(seed))


def expected(realized: RealizedState) -> dict:
    return {
        "seed": realized.seed,
        "route_item_id": ROUTE_Q_ITEM_ID,
        "route_arrival": realized.route_q_arrival,
        "route_arrival_epoch": realized.route_q_arrival_epoch,
        "new_arrival_by": realized.new_arrival_by,
        "hotel_checkin_by": realized.hotel_checkin_by,
        "meeting_confirm_by": realized.meeting_confirm_by,
        "meeting_start": realized.meeting_start,
        "meeting_start_epoch": realized.meeting_start_epoch,
        "transfer_pickup": realized.transfer_pickup,
        "transfer_pickup_epoch": realized.transfer_pickup_epoch,
        "transfer_destination": HOTEL_LOCATION,
        "client_email": realized.client_email,
        "rebook_cap_eur": realized.rebook_cap_eur,
    }


def past_events(event_log) -> list:
    if isinstance(event_log, list):
        return event_log
    inner = event_log.get("event_log", event_log)
    return list(inner.get("past_events") or [])
