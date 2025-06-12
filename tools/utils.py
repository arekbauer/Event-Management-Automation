import datetime as dt 
from datetime import datetime
from tools.log_tool import get_logger

from googleapiclient.errors import HttpError

log = get_logger()

def add_events(
    service, 
    calendarID: str,
    event: dict, 
    duplicate_check: bool = True
    ) -> None:
    """Function to add events to calendar"""
    try: 
        if duplicate_check:
            if is_duplicate(service, calendarID, event['start']['dateTime'], event['end']['dateTime']):
                event = service.events().insert(calendarId=calendarID, body=event).execute()
                log.info(f"Event '{event['summary']}' created")
            else:
                log.info(f"Time slot for event '{event['summary']}' is not available. Event not created.")
        else:
            event = service.events().insert(calendarId=calendarID, body=event).execute()
            log.info(f"Event '{event['summary']}' created")

    except HttpError as error: 
        log.error("An error has occured", error)

def is_duplicate(service, calendar_id: str, start: str, end: str) -> bool:
    """Function to check if the event already exists in the calendar"""
    # Grabs any events between the start and end time
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return len(events) == 0


def delete_future_events(service, calendar_id: str) -> None:
    """Function to delete all the events in given calendar ID"""
    # Grab the current date and time
    now = datetime.now(dt.timezone.utc)
    tomorrow = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_iso = tomorrow.isoformat()
    tomorrow_date = tomorrow.date().isoformat()
    
    # Fetch events starting from the current time (now)
    events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

    # Get the list of events from the response
    events = events_result.get('items', [])
    if not events:
        log.info("No more future events to delete.")
        return 
    
    for event in events:
        try:
            # Get the event start time (dateTime) or start date (date) for all-day events
            event_start = event.get('start').get('dateTime', event.get('start').get('date'))
            
            # Check if the event is an all-day event (has date but no time)
            if 'date' in event.get('start'):
                # Only delete all-day events starting after today (i.e., tomorrow and beyond)
                if event_start >= tomorrow_date:
                    service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                    log.info(f"Deleted all-day event: {event.get('summary', 'No Summary')}")
            else:
                # Only delete time-specific events starting after today (i.e., tomorrow and beyond)
                if event_start >= tomorrow_iso:
                    service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                    log.info(f"Deleted time-specific event: {event.get('summary', 'No Summary')}")
        except Exception as e:
            log.error(f"Could not delete event: {e}")