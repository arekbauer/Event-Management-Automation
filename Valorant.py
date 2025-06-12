from tools import utils, api_tools as api
from tools.log_tool import get_logger, send_discord_notification
import os
from tools.config import ROOT_FILE_PATH
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def valorant(creds, delete_future_events:bool): 
    """Script for VLR Matches"""
    # Define some variables
    api_url = "https://vlrggapi.vercel.app/match?q=upcoming"
    cache_file = os.path.join(ROOT_FILE_PATH, "json/vlr_matches.json")
    whiteList = ["Valorant Masters Toronto 2025","Champions Tour 2025", "Esports World Cup 2025 "]
        
    log = get_logger()
    log.info("-------------START of VALORANT Script-------------\n")
    
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
        if delete_future_events:
            utils.delete_future_events(service, calendarID)
        
        matches_from_file = api.load_data_from_file(cache_file)
    
        # Check if the loaded data is empty
        if not matches_from_file:  
            send_discord_notification("No matches found in the VALORANT API response. (change the whitelist!)")
            log.warning("The JSON file contains no matches (empty list).")
            return
        
        # Go through each match from json file
        for match in matches_from_file:
            # Converts a VLR format to Google Calendar format
            event = api.create_vlr_event(match)
            
            # Adds event to calendar
            utils.add_events(service, calendarID, event)     
    else:
        send_discord_notification("Nothing found in the VALORANT API response. (check the API call!)")
        log.warning("No matches found in the API response.")
    
    log.info("-------------END of VALORANT Script-------------\n")