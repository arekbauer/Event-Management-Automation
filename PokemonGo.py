from tools import utils, api_tools as api, poke_utils as poke
from tools.log_tool import get_logger

from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def pokemon_go(creds, delete_future_events:bool): 
    """Script for Pokemon Go Events"""
    # Define some variables
    api_url = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
    cache_file = "json/pokemonGo_events.json"
    whiteList = ["community-day", "event", 
                 "live-event", "pokemon-go-fest", "pokemon-spotlight-hour", 
                 "season", "pokemon-go-tour", "raid-day", "elite-raids", 
                 "raid-battles", "raid-hour", "raid-weekend", "go-battle-league"] # Make sure to edit whiteList in all_day_event() if have to

    log = get_logger()
    log.info("--------------START of PokemonGo Script-------------")
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
    if delete_future_events:
        utils.delete_future_events(service, calendarID)
      
    # Go through each event from json file
    for event in api.load_data_from_file(cache_file):      
   
        # Converts a LeekDuck format to Google Calendar format
        new_event = poke.create_pokemon_go_event(event)
        
        # Adds event to calendar
        utils.add_events(service, calendarID, new_event, duplicate_check=False) 
        
    log.info("-------------END of PokemonGo Script-------------\n")