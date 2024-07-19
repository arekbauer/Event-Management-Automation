"""
By using https://github.com/bigfoott/ScrapedDuck

I want to grab events and only put in the start of it, e.g.

- Start of when a new raid boss comes in 
- Full events
- Changing descriptions when event is known
- Hosting all of this on the raspberry pi
"""
import os.path
import datetime as dt 
from datetime import datetime
import utils
import api_tools as api
import logging
import poke_utils as poke

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main(): 
    """Script for Pokemon Go Events"""
    
    # Fetch the data from the API
    data = api.fetch_api_data(api_url)
    
    # Filter wanted events
    event_list = poke.filter_event_types(data, whiteList)
    
    # Save the matches to an external json file
    api.save_data_to_file(event_list, cache_file)
    
    # Set some variables
    service = build("calendar","v3", credentials=creds)
    calendarID = "1c565d24c2befe1ade79037bc085ab3b72fc1860cc463f6547d2e585253e26cf@group.calendar.google.com"
    
    # Do you want to delete all future events in the calendar? 
    utils.delete_future_events(service, calendarID)
      
    # Go through each event from json file
    for event in api.load_data_from_file(cache_file):      
   
        # Converts a LeekDuck format to Google Calendar format
        new_event = poke.create_pokemon_go_event(event)
        
        # Adds event to calendar
        utils.add_events(service, calendarID, new_event, duplicate_check=False) 
            
                
if __name__ == "__main__":
    """Handles all of Google OAuth"""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("json/token.json"):
        creds = Credentials.from_authorized_user_file("json/token.json", SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("json/credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
    
        # Save the credentials for the next run
        with open("json/token.json", "w") as token:
            token.write(creds.to_json())
            
    # Define some variables
    api_url = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
    cache_file = "json/pokemonGo_events.json"
    whiteList = ["community-day", "event", 
                 "live-event", "pokemon-go-fest", "pokemon-spotlight-hour", 
                 "season", "pokemon-go-tour", "raid-day", "elite-raids", 
                 "raid-battles", "raid-hour", "raid-weekend", "go-battle-league"] # Make sure to edit whiteList in all_day_event() if have to
    
    main()