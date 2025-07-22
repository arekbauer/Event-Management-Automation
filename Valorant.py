from tools import utils, api_tools as api
from tools.log_tool import get_logger, send_discord_notification
import os
from tools.config import ROOT_FILE_PATH
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def valorant(creds, delete_future_events: bool) -> None:
    """Script for VLR Matches with API Fallback and full workflow."""
    cache_file = os.path.join(ROOT_FILE_PATH, "json/vlr_matches.json")
    whiteList = ["VCT 2025: Pacific Stage 2", "Valorant Champions Tour 2025", "VCT 2025: EMEA Stage 2",
                 "VCT 2025: Americas Stage 2"]
    log = get_logger()
    
    log.info("-------------START of VALORANT Script-------------\n")

    # Step 1: Fetch raw data using the fallback logic
    matches, source = api.fetch_valorant_matches(log)

    if not (matches and source):
        send_discord_notification("CRITICAL: Both VALORANT APIs failed to respond.")
        log.warning("No matches found from any API source.")
        return

    # Step 2: Normalize the raw data into a standard format
    match_list = api.normalise_and_filter_matches(matches, source, whiteList)
    
    # Optional: Save the clean, normalized data for debugging
    # This now requires the json_datetime_serializer helper.
    api.save_data_to_file(match_list, cache_file)

    if not match_list:
        send_discord_notification("VALORANT: No matches found after whitelist filtering.")
        log.warning("The list of matches is empty after applying the whitelist.")
        return

    # Setup Google Calendar Service
    service = build("calendar", "v3", credentials=creds)
    calendarID = "871cadf79004e379fc8630cbcf69b75d050eb8a581b71fddd02ed3a1f4f69034@group.calendar.google.com"
    
    if delete_future_events:
        utils.delete_future_events(service, calendarID)
    
    log.info(f"Processing {len(match_list)} filtered matches...")
    # Loop directly over the clean, normalized list
    for match in match_list:
        utc_datetime_obj = match.get('start_datetime_utc')
        
        if utc_datetime_obj:
            # Step 4: Create the event body for the API
            event = api.create_vlr_event(match)
            
            # Step 5: Add the event to the calendar
            utils.add_events(service, calendarID, event)
    
    log.info("-------------END of VALORANT Script-------------\n")