from datetime import datetime, timedelta, timezone
import os.path
import json
import pytz
import requests
from tools.log_tool import get_logger

log = get_logger()

def fetch_api_data(api_url: str) -> dict | None:
    """Fetches data from the given API URL and return the JSON response"""
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json()
    
    except requests.exceptions.RequestException as e:
        log.error(f"Request failed: {e}") 
        return
    
def fetch_valorant_matches(log):
    """
    Tries to fetch matches from the primary API first. If it fails,
    it falls back to the secondary API.
    Returns the data and a source identifier ('primary' or 'secondary').
    """
    primary_api_url = "https://vlr.orlandomm.net/api/v1/matches"
    secondary_api_url = "https://vlrggapi.vercel.app/match?q=upcoming"

    # --- Try Primary API ---
    log.info("Attempting to fetch data from Primary API...")
    primary_response = fetch_api_data(primary_api_url)
    primary_matches = primary_response.get('data', [])
    
    if primary_matches:
        log.info("Successfully fetched data from Primary API.")
        return primary_matches, 'primary'

    # --- Try Secondary API ---
    log.warning("Primary API failed. Falling back to Secondary API...")
    secondary_response = fetch_api_data(secondary_api_url)
    secondary_matches = secondary_response.get('data', {}).get('segments', [])

    if secondary_matches:
        log.info("Successfully fetched data from Secondary API.")
        return secondary_matches, 'secondary'

    log.error("Both APIs failed to return data.")
    return None, None

def normalise_and_filter_matches(matches: list, source: str, whiteList: list) -> list:
    """
    Normalises raw API data into a standard format, creating a timezone-aware
    datetime object for the start time, and then filters the results.
    """
    NEW_API_TIME_OFFSET_HOURS = 5  # Adjust this if the API changes its time offset
    standardised_list = []
    
    for match in matches:
        dt_object_utc = None
        match_data = {}

        # --- Part 1: Create a standard datetime object from the source ---
        if source == 'primary':
            if match.get('status') != 'Upcoming':
                continue

            iso_string = match.get('utc')
            if iso_string:
                dt_object_utc = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
                
                # Apply the 5-hour offset if it's greater than 0
                if NEW_API_TIME_OFFSET_HOURS > 0:
                    dt_object_utc += timedelta(hours=NEW_API_TIME_OFFSET_HOURS)

        elif source == 'secondary':
            date_string = match.get('unix_timestamp')
            if date_string:
                try:
                    # Parse the naive string and make it timezone-aware by setting its tz to UTC
                    unaware_dt = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
                    dt_object_utc = unaware_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    print(f"Warning: Could not parse date '{date_string}'")
                    continue

        if not dt_object_utc:
            continue

        # --- Part 2: Build the standard match_data dictionary ---
        if source == 'primary':
            teams = match.get('teams', [])
            if len(teams) < 2: continue
            
            match_data = {
                "team1": teams[0].get('name'),
                "team2": teams[1].get('name'),
                "match_series": match.get('event'),
                "match_event": match.get('tournament'),
                "match_page": f"https://www.vlr.gg/{match.get('id')}",
                "start_datetime_utc": dt_object_utc
            }
        elif source == 'secondary':
            match_data = {
                "team1": match.get('team1'),
                "team2": match.get('team2'),
                "match_series": match.get('match_series'),
                "match_event": match.get('match_event'),
                "match_page": match.get('match_page'),
                "start_datetime_utc": dt_object_utc
            }

        # --- Part 3: Filter based on the whitelist ---
        event_info = f"{match_data.get('match_event', '')} {match_data.get('match_series', '')}"
        if any(phrase in event_info for phrase in whiteList):
            standardised_list.append(match_data)
            
    return standardised_list

def extract_vlr_matches(matches: dict, whiteList: list = None) -> list:
    """Extract relevant information from each match and return a list of dictionaries"""
    extracted_data = []
    for match in matches:
        match_data = {
            "team1": match.get('team1'),
            "team2": match.get('team2'),
            "time_until_match": match.get('time_until_match'),
            "match_series": match.get('match_series'),
            "match_event": match.get('match_event'),
            "unix_timestamp": match.get('unix_timestamp'),
            "match_page": match.get('match_page')
        }
        
        # Check if any whitelist phrase is in match_event or match_series
        if any(phrase in match_data['match_event'] or phrase in match_data['match_series'] for phrase in whiteList):
            extracted_data.append(match_data)
            
    return extracted_data

def create_vlr_event(match: dict) -> dict:
    """Converts the VLR json format to Google Calendar json format"""
    # Check if it's a Bo5 match
    if "Lower Final" in match['match_series'] or "Grand Final" in match['match_series']:
        duration = 4
    else:
        duration = 2

    # Get the start time and end time in ISO format
    start_time, end_time = convert_time_iso(match['start_datetime_utc'], duration) 
    description = (
        f"Series: {match.get('match_series', 'N/A')}\n"
        f"Event: {match.get('match_event', 'N/A')}\n"
        f"Link: {match.get('match_page', 'N/A')}"
    )
    event = {
        "summary": f"{match['team1']} vs {match['team2']} | {match['match_series']}",
        "description": description,
        "colorId": "6",
        "start": {
            "dateTime": start_time,
            'timeZone': 'Europe/London'
        },
        "end": {
            "dateTime": end_time,
            'timeZone': 'Europe/London'
        },
        "reminders": {
            "useDefault": False
        }
    }
    return event
    
def convert_time_iso(dt_utc: datetime, duration: int) -> tuple[str, str]:
    """
    Converts a timezone-aware UTC datetime object to a localized
    ISO 8601 string for the Google Calendar API.
    """
    bst_timezone = pytz.timezone('Europe/London') 

    # Convert the UTC datetime object to your local timezone
    bst_dt = dt_utc.astimezone(bst_timezone)

    # Format the datetime object as ISO 8601 with timezone offset
    start_time = bst_dt.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Calculate end time
    end_dt = bst_dt + timedelta(hours=duration)
    end_time = end_dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    
    return start_time, end_time
    
def save_data_to_file(data: list, filename: str) -> None:
    """Save data to a JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, default=json_datetime_serializer, indent=4)
        log.info(f"Data saved to {filename}")
        
    except IOError as e:
        log.error(f"Failed to save data to {filename}: {e}")

def load_data_from_file(filename: str) -> list | None:
    """Load data from a JSON file"""
    if not os.path.exists(filename):
        log.warning(f"{filename} does not exist.")
        return None
    
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
        log.info(f"Data loaded from {filename}")
        return data
    
    except IOError as e:
        log.error(f"Failed to load data from {filename}: {e}")
        return None
    
def json_datetime_serializer(obj):
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat() # Convert datetime to an ISO string
    raise TypeError(f"Type {type(obj)} not serializable")
