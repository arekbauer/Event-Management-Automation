import os.path
import datetime as dt 
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
    
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    # open the fixture list you want
    with open("EMEA_stage2.json") as fixtures: 
        fixture_list = json.load(fixtures)
    
    # Do the juicy stuff
    try:
        service = build("calendar","v3", credentials=creds)
        calendarID = "871cadf79004e379fc8630cbcf69b75d050eb8a581b71fddd02ed3a1f4f69034@group.calendar.google.com"
        
        # Do you want to delete all current events in the calendar? 
        #delete_all_events(service, calendarID)
        
        # for each fixture in the json file...
        for fixture in fixture_list:
            start = fixture['start']['dateTime']
            end = fixture['end']['dateTime']
            
            if is_duplicate(service, calendarID, start, end):
                event = service.events().insert(calendarId=calendarID, body=fixture).execute()
                print(f"Event '{fixture['summary']}' created")
            else:
                print(f"Time slot for event '{fixture['summary']}' is not available. Event not created.")
            
    except HttpError as error: 
        print("An error has occured", error)
        
'''Function to check if the event already exists in the calendar'''
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

'''Function to delete all the events in given calendar ID'''
def delete_all_events(service, calendar_id):
    events = service.events().list(calendarId=calendar_id).execute()
    for event in events.get('items', []):
        try:
            service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
            print(f"Deleted event: {event['summary']}")
        except Exception as e:
            print(f"An error occurred: {e}")
                
if __name__ == "__main__":
    main()