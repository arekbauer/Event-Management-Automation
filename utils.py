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
    now = datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    events = service.events().list(calendarId=calendar_id).execute()
    for event in events.get('items', []):
        start = event.get('start').get('dateTime', event.get('start').get('date'))
        if start >= now:
            try:
                service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                print(f"Deleted event: {event['summary']}")
            except Exception as e:
                print(f"An error occurred: {e}")