import os.path
import datetime as dt 
import json
from datetime import datetime
import requests
import logging

from googleapiclient.errors import HttpError

"""Function to add events to calendar"""
def add_events(service, calendarID, event, duplicate_check=True):
    try: 
        if duplicate_check:
            if is_duplicate(service, calendarID, event['start']['dateTime'], event['end']['dateTime']):
                event = service.events().insert(calendarId=calendarID, body=event).execute()
                print(f"Event '{event['summary']}' created")
            else:
                print(f"Time slot for event '{event['summary']}' is not available. Event not created.")
        else:
            event = service.events().insert(calendarId=calendarID, body=event).execute()
            print(f"Event '{event['summary']}' created")

    except HttpError as error: 
        print("An error has occured", error)

"""Function to check if the event already exists in the calendar"""
def is_duplicate(service, calendar_id, start, end):
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


"""Function to delete all the events in given calendar ID"""
def delete_future_events(service, calendar_id):
    # Grab the current date and time
    now = datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today = datetime.now(dt.timezone.utc).date().isoformat()
    
    # Fetch events starting from the current time (now)
    events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

    # Get the list of events from the response
    events = events_result.get('items', [])
    if not events:
        print("No more future events to delete.")
        return 
    
    for event in events:
        try:
            # Get the event start time (dateTime) or start date (date) for all-day events
            event_start = event.get('start').get('dateTime', event.get('start').get('date'))
            
            # Check if the event is an all-day event (has date but no time)
            if 'date' in event.get('start'):
                if event_start >= today:
                    service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                    print(f"Deleted all-day event: {event.get('summary', 'No Summary')}")
            else:
                if event_start >= now:
                    service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                    print(f"Deleted time-specific event: {event.get('summary', 'No Summary')}")
        except Exception as e:
            print(f"Could not delete event: {e}")