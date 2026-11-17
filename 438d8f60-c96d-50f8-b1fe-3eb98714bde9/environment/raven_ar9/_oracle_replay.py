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

from are.simulation.apps.email_client import EmailFolderName
from are.simulation.environment import Environment, EnvironmentConfig
from are.simulation.types import CompletedEvent, EventMetadata, EventRegisterer, EventType

from raven_ar9 import _oracle_truth as truth
from raven_ar9 import statedump
from raven_ar9.clock import DeterministicClock
from raven_ar9.realize import (
    AIRPORT_LOCATION,
    CAB_SERVICE_TYPE,
    CLIENT_EMAIL,
    CLIENT_NAME,
    CLIENT_SITE_LOCATION,
    HOTEL_FRONTDESK_EMAIL,
    HOTEL_LOCATION,
    HOTEL_NAME,
    LOUNGE_ITEM_ID,
    MEETING_DURATION_SECONDS,
    ROUTE_P_ITEM_ID,
    ROUTE_Q_ITEM_ID,
    ROUTE_R_ITEM_ID,
    ROUTE_Q_LABEL,
    START_TIME,
    T_EMAIL,
    to_stamp,
)
from raven_ar9.scenario import (
    RavenAR9,
    cutoff_marker_email,
    trip_brief_email,
)

DEFAULT_EVENTLOG = "logs/artifacts/eventlog.json"
STEP_SECONDS = 20.0
UNTICKED_STEPS = frozenset({"advance", "deliver_discovery", "read_discovery", "cutoff", "fire_async", "derive_route"})


class SimClock:
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
        target = float(epoch)
        if target > self.now():
            self.set(target)


class OracleRun:
    def __init__(self, seed: int | None = None):
        self.realized = truth.realize(seed)
        RavenAR9._injected_realized = self.realized
        self.scenario = RavenAR9()
        self.scenario.initialize()
        self.apps = {app.name: app for app in self.scenario.apps}
        self.env = Environment(
            config=EnvironmentConfig(
                start_time=START_TIME,
                duration=self.scenario.duration,
                time_increment_in_seconds=self.scenario.time_increment_in_seconds,
                oracle_mode=False,
                queue_based_loop=False,
                exit_when_no_events=False,
            )
        )
        self.env.register_apps(self.scenario.apps)
        self.clock = SimClock(self.env.time_manager, START_TIME)
        self.deterministic_clock = DeterministicClock(self.env)
        self.route_item: str | None = None
        self.order_id: str | None = None
        self.ride_id: str | None = None
        self.meeting_event_id: str | None = None

    def _shop(self):
        return self.apps["ShoppingApp"]

    def _flip_routes(self) -> None:
        from raven_ar9.scenario import _flip_routes_available

        _flip_routes_available(self._shop())

    def step_deliver_discovery(self) -> None:
        self.clock.advance_to(START_TIME + T_EMAIL)
        self.apps["Emails"].add_email(trip_brief_email(self.realized), EmailFolderName.INBOX)

    def step_read_discovery(self) -> None:
        inbox = self.apps["Emails"].folders[EmailFolderName.INBOX]
        briefs = [m for m in inbox.emails if "NEW_ARRIVAL_BY:" in (m.content or "")]
        if not briefs:
            raise RuntimeError("trip brief absent from inbox")

    def step_fire_async(self, key: str) -> None:
        from raven_ar9.realize import ASYNC_EVENT_OFFSETS
        from raven_ar9.scenario import B2_SUBJECT, B3_SUBJECT, B4_SUBJECT, _notice

        self.clock.advance_to(START_TIME + ASYNC_EVENT_OFFSETS[key])
        emails = self.apps["Emails"]
        with EventRegisterer.disable():
            if key == "B2":
                emails.add_email(
                    _notice("notices@monsoonair.example", B2_SUBJECT,
                            "Dublin-Madrid delayed; Madrid-Lisbon connection missed.",
                            ASYNC_EVENT_OFFSETS[key]),
                    EmailFolderName.INBOX,
                )
            elif key == "B3":
                self._flip_routes()
                emails.add_email(
                    _notice("notices@monsoonair.example", B3_SUBJECT,
                            "Rebooking options are now in your catalogue.",
                            ASYNC_EVENT_OFFSETS[key]),
                    EmailFolderName.INBOX,
                )
            elif key == "B4":
                emails.add_email(
                    _notice(CLIENT_EMAIL, B4_SUBJECT,
                            f"Our review is set for {self.realized.meeting_start} UTC. "
                            f"If you land after {to_stamp(self.realized.b4_threshold_epoch)} UTC "
                            f"we move to 09:00 next day; otherwise it stands. - {CLIENT_NAME}",
                            ASYNC_EVENT_OFFSETS[key]),
                    EmailFolderName.INBOX,
                )

    def step_derive_route(self, item_id: str | None = None) -> None:
        self.route_item = item_id or ROUTE_Q_ITEM_ID

    def step_rebook_route(self) -> None:
        if self.route_item is None:
            raise RuntimeError("route not derived; run derive_route first")
        shop = self._shop()
        shop.add_to_cart(item_id=self.route_item, quantity=1)
        self.order_id = shop.checkout()

    def step_book_meeting(self) -> None:
        realized = self.realized
        self.meeting_event_id = self.apps["Calendar"].add_calendar_event(
            title=f"Azul Freight review - {CLIENT_NAME}",
            start_datetime=realized.meeting_start,
            end_datetime=to_stamp(realized.meeting_start_epoch + MEETING_DURATION_SECONDS),
            tag="client",
            description="Rescheduled client review after the transit disruption.",
            location=CLIENT_SITE_LOCATION,
            attendees=[CLIENT_EMAIL],
        )

    def step_order_transfer(self, ride_time: str | None = None, end_location: str | None = None) -> None:
        ride = self.apps["CabApp"].order_ride(
            start_location=AIRPORT_LOCATION,
            end_location=end_location if end_location is not None else HOTEL_LOCATION,
            service_type=CAB_SERVICE_TYPE,
            ride_time=ride_time or self.realized.transfer_pickup,
        )
        self.ride_id = ride.ride_id

    def step_hotel_hold(self) -> None:
        realized = self.realized
        self.apps["Emails"].send_email(
            recipients=[HOTEL_FRONTDESK_EMAIL],
            subject=f"Late arrival - please hold the room ({realized.route_q_arrival} UTC)",
            content=(
                f"Hello, my flight now lands at {realized.route_q_arrival} UTC, before your "
                f"check-in cutoff. Please hold my pre-paid room at {HOTEL_NAME}. - Caleb Marsh"
            ),
        )

    def step_notify_client(self, channel: str = "Emails") -> None:
        realized = self.realized
        body = (
            f"Hi {CLIENT_NAME}, my rebooked flight lands at {realized.route_q_arrival} UTC, "
            f"before your threshold, so our review stands at {realized.meeting_start} UTC. "
            f"See you then. - Caleb"
        )
        if channel == "Emails":
            self.apps["Emails"].send_email(
                recipients=[CLIENT_EMAIL],
                subject="Lisbon arrival confirmed - review stands",
                content=body,
            )
        else:
            self.apps[channel].send_message(user_id="contact_0507", content=body)

    def step_confirm(self, content: str | None = None) -> None:
        realized = self.realized
        body = content or (
            f"Done. Rebooked the {ROUTE_Q_LABEL} flight landing {realized.route_q_arrival} UTC "
            f"(within the EUR {int(realized.rebook_cap_eur)} cap), booked the airport transfer to "
            f"{HOTEL_NAME} at {realized.transfer_pickup} UTC, asked the hotel to hold the room, "
            f"and told {CLIENT_NAME} the review stands at {realized.meeting_start} UTC."
        )
        self.apps["AgentUserInterface"].send_message_to_user(content=body)

    def step_lazy_note(self) -> None:
        from raven_ar9.realize import COLLEAGUE_EMAIL

        self.apps["Emails"].send_email(
            recipients=[COLLEAGUE_EMAIL],
            subject="Flights sorted",
            content="Booked the Lisbon flight and the airport cab. Will tidy up the rest later.",
        )

    def step_cutoff(self) -> None:
        self.clock.advance_to(self.realized.meeting_confirm_by_epoch)
        self.apps["Emails"].add_email(cutoff_marker_email(), EmailFolderName.INBOX)

    def step_advance(self, seconds: float | None = None, to: float | None = None) -> None:
        if to is not None:
            self.clock.advance_to(float(to))
        else:
            self.clock.advance(float(seconds or 0))

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
        did_mutate = any(
            (entry.get("action") or {}).get("operation_type") == "write"
            and not (
                (entry.get("action") or {}).get("app_name") == "Emails"
                and (entry.get("action") or {}).get("function_name") == "add_email"
            )
            for entry in entries
        )
        return {
            "seed": self.realized.seed,
            "event_log": event_log,
            "clock": self.deterministic_clock.manifest(),
            "appstate": statedump.build_appstate(self.scenario.apps) if did_mutate else None,
            "sim_time_end": self.clock.now(),
        }


def oracle_actions(seed: int | None = None, channel: str = "Emails") -> list[tuple[str, dict]]:
    return [
        ("deliver_discovery", {}),
        ("read_discovery", {}),
        ("fire_async", {"key": "B2"}),
        ("fire_async", {"key": "B3"}),
        ("derive_route", {}),
        ("rebook_route", {}),
        ("fire_async", {"key": "B4"}),
        ("book_meeting", {}),
        ("order_transfer", {}),
        ("hotel_hold", {}),
        ("notify_client", {"channel": channel}),
        ("confirm", {}),
        ("cutoff", {}),
    ]


def alternate_messages(seed: int | None = None) -> list[tuple[str, dict]]:
    return oracle_actions(seed, channel="Messages")


def control_noop(seed: int | None = None) -> list[tuple[str, dict]]:
    return [("deliver_discovery", {}), ("read_discovery", {}), ("cutoff", {})]


def control_wrong_route(seed: int | None = None) -> list[tuple[str, dict]]:
    return [
        step if step[0] != "derive_route" else ("derive_route", {"item_id": ROUTE_P_ITEM_ID})
        for step in oracle_actions(seed)
    ]


def control_over_cap(seed: int | None = None) -> list[tuple[str, dict]]:
    return [
        step if step[0] != "derive_route" else ("derive_route", {"item_id": ROUTE_R_ITEM_ID})
        for step in oracle_actions(seed)
    ]


def control_stale_transfer(seed: int | None = None) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    stale_pickup = to_stamp(truth.realize(seed).orig_arrival_epoch + 1200.0)
    for step in oracle_actions(seed):
        if step[0] == "order_transfer":
            out.append(("order_transfer", {"ride_time": stale_pickup}))
        else:
            out.append(step)
    return out


def control_lazy_partial(seed: int | None = None) -> list[tuple[str, dict]]:
    return [
        ("deliver_discovery", {}),
        ("read_discovery", {}),
        ("fire_async", {"key": "B2"}),
        ("fire_async", {"key": "B3"}),
        ("derive_route", {}),
        ("rebook_route", {}),
        ("order_transfer", {}),
        ("lazy_note", {}),
        ("confirm", {}),
        ("cutoff", {}),
    ]


ALTERNATES = {"alt1_messages": alternate_messages}
CONTROLS = {
    "noop": control_noop,
    "wrong_route": control_wrong_route,
    "over_cap": control_over_cap,
    "stale_transfer": control_stale_transfer,
    "lazy_partial": control_lazy_partial,
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


def expected_full_success(mode: str) -> bool:
    return mode == "oracle" or mode in ALTERNATES


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


def replay_to_authority() -> dict:
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
