from datetime import datetime, timedelta
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

    # Convert time to valid format 
    start_time, end_time = convert_time_iso(match['unix_timestamp'], duration) 
    event = {
        #"summary": f"{match['team1']} vs {match['team2']} | {match['match_event']} - {match['match_series']}",
        "summary": f"{match['team1']} vs {match['team2']} | {match['match_series']}",
        "description": f"{match['match_page']}",
        "colorId": "6",
        "start": {
            "dateTime": start_time
        },
        "end": {
            "dateTime": end_time
        },
        "reminders": {
            "useDefault": False
        }
    }
    return event
    
def convert_time_iso(timestamp: str, duration: int) -> tuple[str, str]:
    """Convert Unix timestamp (string) to ISO 8601 format with timezone offset"""
    # Parse the Unix timestamp into a datetime object
    dt_object = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

    # Assume the timestamp is UTC and convert to your desired timezone
    utc_timezone = pytz.timezone('UTC')
    bst_timezone = pytz.timezone('Europe/London')  

    utc_dt = utc_timezone.localize(dt_object) 
    bst_dt = utc_dt.astimezone(bst_timezone)

    # Format the datetime object as ISO 8601 with timezone offset
    start_time = bst_dt.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Calculate end time by adding duration_hours
    end_dt = bst_dt + timedelta(hours=duration)
    end_time = end_dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    
    return start_time, end_time
    

def save_data_to_file(data: list, filename: str) -> None:
    """Save data to a JSON file"""
    try:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4)
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
