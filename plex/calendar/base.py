from datetime import datetime, timedelta
from gcsa.google_calendar import GoogleCalendar
from gcsa.event import Event
from plex.secrets import email  # you need to create this file
import random
import functools

EVENT_ID_ENCODING = "0123456789abcdefghijklmnopqrstuv"
# added to the start of the uuid. Chars must be a part of EVENT_ID_ENCODING
CALENDAR_EVENT_IDENTIFIER = "ple88ple88ple88ple88ple88ple88"
GENERATED_EVENT_ID_LENGTH = 888


def validate_event_id(event_id: str):
    assert len(event_id) < 1024
    for char in event_id:
        assert (
            char in EVENT_ID_ENCODING
        ), f"Char in '{event_id}' is '{char}' but must be one of {EVENT_ID_ENCODING}"


@functools.cache
def get_calendar():
    return GoogleCalendar(email)


def generate_event_id(additional_id: str = "") -> str:
    event_id = (
        CALENDAR_EVENT_IDENTIFIER
        + additional_id
        + "".join(
            [random.choice(EVENT_ID_ENCODING) for _ in range(GENERATED_EVENT_ID_LENGTH)]
        )
    )
    validate_event_id(event_id)
    return event_id


def is_event_is_plex_generated_event(event: Event, additional_id: str = "") -> bool:
    return event.id.startswith(CALENDAR_EVENT_IDENTIFIER + additional_id)


def create_calendar_event(
    summary: str, start: datetime, end: datetime, notes: str = "", date_id: str = ""
) -> str:
    event_id = generate_event_id(date_id)
    event = Event(
        summary=summary,
        start=start,
        end=end,
        event_id=event_id,
        minutes_before_popup_reminder=0,
        description=notes,
    )
    get_calendar().add_event(event)
    return event_id


def update_calendar_event(
    event_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    notes: str = "",
    date_id: str = "",
) -> None:
    event = Event(
        summary=summary,
        start=start,
        end=end,
        event_id=event_id,
        minutes_before_popup_reminder=0,
        description=notes,
    )
    get_calendar().update_event(event)


def get_all_plex_calendar_events(min_date: datetime, date_id: str = "") -> list[Event]:
    events = [
        i
        for i in get_calendar().get_events(time_min=min_date)
        if is_event_is_plex_generated_event(i, date_id)
    ]
    return events


def get_event(event_id: str) -> Event:
    return get_calendar().get_event(event_id)


def delete_calendar_event(
    event: Event = None,
) -> None:
    get_calendar().delete_event(event)
