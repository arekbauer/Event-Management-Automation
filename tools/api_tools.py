from datetime import datetime, timedelta
import os.path
import json
import pytz
import requests
from tools.log_tool import get_logger

log = get_logger()

"""Fetch data from the given API URL and return the JSON response"""
def fetch_api_data(api_url):
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json()
    
    except requests.exceptions.RequestException as e:
        log.error(f"Request failed: {e}") 
        return 

"""Extract relevant information from each match and return a list of dictionaries"""
def extract_vlr_matches(matches, whiteList=None):
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

"""Converts the VLR json format to Google Calendar json format"""
def create_vlr_event(match):
    # TODO: If the "match_event" contains "Lower" or "Ground" and "Final" then it's a Bo5 - so 
    #   convert_time_iso(duration = 4) not duration = 2
      
    # Convert time to valid format 
    start_time, end_time = convert_time_iso(match['unix_timestamp'])
    event = {
        "summary": f"{match['team1']} vs {match['team2']} | {match['match_event'].split(':', 1)[1].strip()} - {match['match_series']}",
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
    
"""Convert Unix timestamp (string) to ISO 8601 format with timezone offset"""
def convert_time_iso(timestamp, duration=2):
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
    

"""Save data to a JSON file"""
def save_data_to_file(data, filename):
    try:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4)
        log.info(f"Data saved to {filename}")
        
    except IOError as e:
        log.error(f"Failed to save data to {filename}: {e}")

"""Load data from a JSON file"""
def load_data_from_file(filename):
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
