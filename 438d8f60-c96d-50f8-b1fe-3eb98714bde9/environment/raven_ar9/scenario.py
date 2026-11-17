from __future__ import annotations

import os

from are.simulation.apps.apartment_listing import Apartment
from are.simulation.apps.cab import Ride
from are.simulation.apps.calendar import CalendarEvent
from are.simulation.apps.contacts import Contact
from are.simulation.apps.email_client import Email, EmailFolderName
from are.simulation.apps.messaging_v2 import ConversationV2, MessageV2
from are.simulation.apps.shopping import Item, Product
from are.simulation.data_handler.importer import JsonScenarioImporter
from are.simulation.environment import AbstractEnvironment
from are.simulation.scenarios.scenario import Scenario, ScenarioValidationResult
from are.simulation.scenarios.utils.registry import register_scenario
from are.simulation.types import Event, EventRegisterer, EventType

from raven_ar9.realize import (
    ASYNC_EVENT_IDS,
    ASYNC_EVENT_OFFSETS,
    CAB_SEED_DISTANCE_KM,
    CAB_SERVICE_TYPE,
    CLIENT_EMAIL,
    CLIENT_NAME,
    CUTOFF_EVENT_ID,
    DISCOVERY_EVENT_ID,
    DURATION_SECONDS,
    AIRPORT_LOCATION,
    HOTEL_LOCATION,
    HOTEL_DOC_PATH,
    LOUNGE_ITEM_ID,
    LOUNGE_PRICE,
    LOUNGE_PRODUCT_ID,
    LOUNGE_PRODUCT_NAME,
    PASSPORT_DOC_PATH,
    PLANT_OFFSET_SECONDS,
    POLICY_DOC_PATH,
    REBOOK_PRODUCT_ID,
    REBOOK_PRODUCT_NAME,
    SCENARIO_ID,
    START_TIME,
    T_EMAIL,
    TIME_INCREMENT_SECONDS,
    TRANSFER_DOC_PATH,
    TRIP_DESK_SENDER,
    TRIP_DESK_SUBJECT,
    TRIP_DIR,
    UNIVERSE_APP_COUNT,
    USER_CONTACT_ID,
    USER_EMAIL,
    USER_NAME,
    RealizedState,
    abstention_emails,
    ambient_apartments,
    ambient_calendar_events,
    ambient_contacts,
    ambient_conversations,
    ambient_inbox_emails,
    ambient_products,
    ambient_sent_emails,
    authorization_contacts,
    derive,
    hotel_document,
    passport_document,
    policy_document,
    route_options,
    to_stamp,
    transfer_document,
    trip_brief_body,
)

DEFAULT_SEED = 7742
SEED_ENV_VAR = "RAVEN_EPISODE_SEED"
UNIVERSE_ENV_VAR = "RAVEN_UNIVERSE_PATH"
DEFAULT_UNIVERSE_PATH = "/task/universe_0.json"

CUTOFF_SUBJECT = "Confirmation window closed"
CUTOFF_BODY = (
    f"Caleb,\n\nThe confirmation window for the Lisbon meeting has now closed.\n\n"
    f"Wayfarer Travel Desk\n"
)

B2_SUBJECT = "Flight delay: your Madrid connection is at risk"
B3_SUBJECT = "Rebooking options are now available"
B4_SUBJECT = "Azul Freight meeting - timing"


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


def trip_brief_email(realized: RealizedState) -> Email:
    return Email(
        sender=TRIP_DESK_SENDER,
        recipients=[USER_EMAIL],
        subject=TRIP_DESK_SUBJECT,
        content=trip_brief_body(realized),
        timestamp=START_TIME + T_EMAIL,
    )


def cutoff_marker_email() -> Email:
    return Email(
        sender=TRIP_DESK_SENDER,
        recipients=[USER_EMAIL],
        subject=CUTOFF_SUBJECT,
        content=CUTOFF_BODY,
    )


def _notice(sender: str, subject: str, body: str, offset: float) -> Email:
    return Email(
        sender=sender,
        recipients=[USER_EMAIL],
        subject=subject,
        content=body,
        timestamp=START_TIME + offset,
    )


def _seed_user_contact(contacts) -> None:
    if USER_CONTACT_ID in contacts.contacts:
        return
    first, _, last = USER_NAME.partition(" ")
    contacts.contacts[USER_CONTACT_ID] = Contact(
        first_name=first,
        last_name=last,
        contact_id=USER_CONTACT_ID,
        is_user=True,
        email=USER_EMAIL,
    )


def _seed_contacts(apps_by_name) -> None:
    with EventRegisterer.disable():
        _seed_user_contact(apps_by_name["ContactsApp"])
        for cid, first, last, job, email, app_name in authorization_contacts():
            book = apps_by_name[app_name]
            if cid in book.contacts:
                raise RuntimeError(f"contact id {cid} already present in {app_name}")
            book.contacts[cid] = Contact(
                first_name=first,
                last_name=last,
                contact_id=cid,
                job=job,
                email=email or None,
            )


def _seed_rebooking_catalogue(shopping) -> None:
    variants: dict[str, Item] = {}
    for item_id, price, label, arrival_epoch in route_options():
        variants[item_id] = Item(
            item_id=item_id,
            price=price,
            available=False,
            options={"route": label, "arrival": to_stamp(arrival_epoch)},
        )
    shopping.products[REBOOK_PRODUCT_ID] = Product(
        name=REBOOK_PRODUCT_NAME,
        product_id=REBOOK_PRODUCT_ID,
        variants=variants,
    )
    shopping.products[LOUNGE_PRODUCT_ID] = Product(
        name=LOUNGE_PRODUCT_NAME,
        product_id=LOUNGE_PRODUCT_ID,
        variants={
            LOUNGE_ITEM_ID: Item(
                item_id=LOUNGE_ITEM_ID,
                price=LOUNGE_PRICE,
                available=True,
                options={},
            )
        },
    )


def _seed_cab_quote(cab) -> None:
    cab.quotation_history.append(
        Ride(
            ride_id="quote_seed",
            status="QUOTED",
            service_type=CAB_SERVICE_TYPE,
            start_location=AIRPORT_LOCATION,
            end_location=HOTEL_LOCATION,
            price=None,
            distance_km=CAB_SEED_DISTANCE_KM,
        )
    )


def _write_reference_documents(files, realized: RealizedState) -> None:
    documents = {
        TRANSFER_DOC_PATH: transfer_document(),
        HOTEL_DOC_PATH: hotel_document(realized),
        POLICY_DOC_PATH: policy_document(realized),
        PASSPORT_DOC_PATH: passport_document(),
    }
    with EventRegisterer.disable():
        files.makedirs(TRIP_DIR, exist_ok=True)
        for path, body in documents.items():
            with files.open(path, "w") as handle:
                handle.write(body)


def _seed_plant_emails(emails) -> None:
    with EventRegisterer.disable():
        for index, (sender, subject, body) in enumerate(abstention_emails()):
            emails.add_email(
                Email(
                    sender=sender,
                    recipients=[USER_EMAIL],
                    subject=subject,
                    content=body,
                    timestamp=START_TIME + PLANT_OFFSET_SECONDS + index * 60,
                ),
                folder_name=EmailFolderName.INBOX,
            )


def _register_messaging_users(apps_by_name) -> None:
    books = (apps_by_name["ContactsApp"], apps_by_name["InternalContacts"])
    for name in ("Messages", "Chats"):
        app = apps_by_name[name]
        for book in books:
            for cid, contact in book.contacts.items():
                display = f"{contact.first_name} {contact.last_name}".strip()
                app.id_to_name[cid] = display
                app.name_to_id[display] = cid


def _seed_ambient_contacts(apps_by_name) -> None:
    with EventRegisterer.disable():
        for cid, first, last, job, email, app_name in ambient_contacts():
            book = apps_by_name[app_name]
            if cid in book.contacts:
                continue
            book.contacts[cid] = Contact(
                first_name=first, last_name=last, contact_id=cid, job=job, email=email or None
            )


def _seed_ambient_inbox(emails) -> None:
    with EventRegisterer.disable():
        for index, (sender, subject, body) in enumerate(ambient_inbox_emails()):
            emails.add_email(
                Email(
                    sender=sender, recipients=[USER_EMAIL], subject=subject, content=body,
                    timestamp=START_TIME + PLANT_OFFSET_SECONDS - (index + 1) * 300,
                ),
                folder_name=EmailFolderName.INBOX,
            )


def _seed_ambient_sent(emails) -> None:
    with EventRegisterer.disable():
        for index, (recipient, subject, body) in enumerate(ambient_sent_emails()):
            emails.add_email(
                Email(
                    sender=USER_EMAIL, recipients=[recipient], subject=subject, content=body,
                    timestamp=START_TIME + PLANT_OFFSET_SECONDS - (index + 1) * 450,
                ),
                folder_name=EmailFolderName.SENT,
            )


def _seed_ambient_calendar(calendar) -> None:
    with EventRegisterer.disable():
        for index, (title, start_epoch, end_epoch, tag, location) in enumerate(ambient_calendar_events()):
            event_id = f"raven_ar9_amb_cal_{index:03d}"
            calendar.events[event_id] = CalendarEvent(
                event_id=event_id, title=title, start_datetime=start_epoch,
                end_datetime=end_epoch, tag=tag, description="", location=location, attendees=[],
            )


def _seed_ambient_shopping(shopping) -> None:
    for product_id, name, variants in ambient_products():
        shopping.products[product_id] = Product(
            name=name, product_id=product_id,
            variants={
                iid: Item(item_id=iid, price=price, available=available, options={})
                for iid, price, available in variants
            },
        )


def _seed_ambient_apartments(flat) -> None:
    for apt_id, name, location, price in ambient_apartments():
        flat.apartments[apt_id] = Apartment(
            name=name, location=location, zip_code="1100-000", price=price,
            bedrooms=1, bathrooms=1, property_type="hotel room", square_footage=240,
            furnished_status="furnished", floor_level="mid", pet_policy="no pets",
            lease_term="nightly", apartment_id=apt_id, amenities=["wifi"],
        )


def _seed_ambient_conversations(apps_by_name) -> None:
    with EventRegisterer.disable():
        convos = ambient_conversations()
        for app_name in ("Messages", "Chats"):
            app = apps_by_name[app_name]
            for index, (title, other_id, msgs) in enumerate(convos):
                conversation_id = f"raven_ar9_amb_{app_name.lower()}_{index:03d}"
                base = START_TIME + PLANT_OFFSET_SECONDS - (index + 1) * 600
                messages = [
                    MessageV2(
                        sender_id=sender_id, content=content, timestamp=base + position * 60,
                        message_id=f"{conversation_id}_m{position}",
                    )
                    for position, (sender_id, content) in enumerate(msgs)
                ]
                app.add_conversation(
                    ConversationV2(
                        participant_ids=[USER_CONTACT_ID, other_id], messages=messages,
                        title=title, conversation_id=conversation_id,
                        last_updated=messages[-1].timestamp if messages else base,
                    )
                )


def _flip_routes_available(shopping) -> None:
    product = shopping.products.get(REBOOK_PRODUCT_ID)
    if product is None:
        return
    for item in product.variants.values():
        item.available = True


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
        self.apps = universe_apps
        for name in ("Messages", "Chats"):
            apps_by_name[name].internal_fs = apps_by_name["Files"]
        _seed_contacts(apps_by_name)
        _seed_ambient_contacts(apps_by_name)
        _register_messaging_users(apps_by_name)
        _seed_rebooking_catalogue(apps_by_name["ShoppingApp"])
        _seed_ambient_shopping(apps_by_name["ShoppingApp"])
        _seed_cab_quote(apps_by_name["CabApp"])
        _write_reference_documents(apps_by_name["Files"], self.realized)
        _seed_plant_emails(apps_by_name["Emails"])
        _seed_ambient_inbox(apps_by_name["Emails"])
        _seed_ambient_sent(apps_by_name["Emails"])
        _seed_ambient_calendar(apps_by_name["Calendar"])
        _seed_ambient_apartments(apps_by_name["RentAFlat"])
        _seed_ambient_conversations(apps_by_name)

    def build_events_flow(self) -> None:
        emails = self.get_app("Emails")
        shopping = self.get_app("ShoppingApp")
        realized = self.realized

        def env_notice(sender: str, subject: str, body: str, key: str) -> None:
            with EventRegisterer.disable():
                emails.add_email(
                    _notice(sender, subject, body, ASYNC_EVENT_OFFSETS[key]),
                    folder_name=EmailFolderName.INBOX,
                )

        def sent(subject: str) -> bool:
            folder = emails.folders[EmailFolderName.INBOX]
            return any(mail.subject == subject for mail in folder.emails)

        def apply_b2_delay() -> None:
            if sent(B2_SUBJECT):
                return
            env_notice(
                "notices@monsoonair.example",
                B2_SUBJECT,
                "Your Dublin-Madrid leg is delayed and the Madrid-Lisbon connection can no "
                "longer be made. Rebooking options will follow shortly.",
                "B2",
            )

        def apply_b3_offer() -> None:
            if sent(B3_SUBJECT):
                return
            _flip_routes_available(shopping)
            env_notice(
                "notices@monsoonair.example",
                B3_SUBJECT,
                "Rebooking options to Lisbon are now in your rebooking catalogue. Fares and "
                "arrival times vary; choose one that lands in time and stays within policy.",
                "B3",
            )

        def apply_b4_client() -> None:
            if sent(B4_SUBJECT):
                return
            env_notice(
                CLIENT_EMAIL,
                B4_SUBJECT,
                f"Our review is set for {realized.meeting_start} UTC. If your confirmed landing "
                f"is after {to_stamp(realized.b4_threshold_epoch)} UTC we will move it to 09:00 "
                f"the next day; otherwise it stands. - {CLIENT_NAME}",
                "B4",
            )

        discovery = (
            Event.from_function(
                emails.add_email,
                event_type=EventType.ENV,
                email=trip_brief_email(realized),
                folder_name=EmailFolderName.INBOX,
            )
            .with_id(DISCOVERY_EVENT_ID)
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
            .at_absolute_time(realized.meeting_confirm_by_epoch)
        )

        mutators = {"B2": apply_b2_delay, "B3": apply_b3_offer, "B4": apply_b4_client}
        flow = [discovery, cutoff]
        for key, mutator in mutators.items():
            flow.append(
                Event.from_function(mutator, event_type=EventType.ENV)
                .with_id(ASYNC_EVENT_IDS[key])
                .at_absolute_time(START_TIME + ASYNC_EVENT_OFFSETS[key])
            )
        self.events = flow

    def validate(self, env: AbstractEnvironment) -> ScenarioValidationResult:
        try:
            realized = self.realized
            calendar = self.get_app("Calendar")
            meeting = [
                event
                for event in calendar.events.values()
                if abs(float(event.start_datetime) - realized.meeting_start_epoch) < 1e-6
            ]
            return ScenarioValidationResult(success=bool(meeting))
        except Exception as exc:
            return ScenarioValidationResult(success=False, exception=exc)
