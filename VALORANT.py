import os.path
import logging as log
from tools import utils, api_tools as api
from tools.log_tool import get_logger

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main(): 
    """Script for VLR Matches"""
    # Fetch the data from the API
    events = api.fetch_api_data(api_url)
    matches = events.get('data',{}).get('segments',[])
    
    # Check if matches are present
    if matches: 
        match_list = api.extract_vlr_matches(matches,whiteList) # Extract the details we need from API call
        
        # Save the matches to an external json file
        api.save_data_to_file(match_list, cache_file)
        
        # Set some variables
        service = build("calendar","v3", credentials=creds)
        calendarID = "871cadf79004e379fc8630cbcf69b75d050eb8a581b71fddd02ed3a1f4f69034@group.calendar.google.com"
        
        # Do you want to delete all future events in the calendar? 
        utils.delete_future_events(service, calendarID)
        
        # Go through each match from json file
        for match in api.load_data_from_file(cache_file):
            
            # Converts a VLR format to Google Calendar format
            event = api.create_vlr_event(match)
            
            # Adds event to calendar
            utils.add_events(service, calendarID, event)     
    else:
        log.warning("No matches found in the API response.")
    
    log.info("-----------------END of VALORANT Script-----------------\n")
           
                
if __name__ == "__main__":
    
    # Call logging to start
    log = get_logger()
    log.info("-----------------START of VALORANT Script-----------------")
    
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
    api_url = "https://vlrggapi.vercel.app/match?q=upcoming"
    cache_file = "json/vlr_matches.json"
    whiteList = ["Champions Tour 2024"]
    
    main()