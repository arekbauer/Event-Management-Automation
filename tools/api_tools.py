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
            "team1": match.get('teams')[0].get('name'),
            "team2": match.get('teams')[1].get('name'),
            "event": match.get('event'),
            "tournament": match.get('tournament'),
            "timestamp": match.get('timestamp'),
        }
        
        # Check if any whitelist phrase is in tournament or event
        if any(phrase in match_data['tournament'] or phrase in match_data['event'] for phrase in whiteList):
            extracted_data.append(match_data)

    return extracted_data

"""Converts the VLR json format to Google Calendar json format"""
def create_vlr_event(match):
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
    return tournament

"""Convert Unix timestamp (string) to ISO 8601 format with timezone offset"""
def convert_time_iso(timestamp, duration):
    # Parse the Unix timestamp into a datetime object
    dt_object = datetime.fromtimestamp(int(timestamp))

    # Timestamp is UTC and convert London timezone
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
