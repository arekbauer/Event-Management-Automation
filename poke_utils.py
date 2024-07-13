import os.path
import datetime as dt 
import json
from datetime import datetime
import requests
import logging

"""
TODO:
    Create functions for: 
        - Grabbing certain event types 
        - Filtering Extra details - event bonuses, can be shiny etc. 
        - If its a raid hour or new event - only grab the start date, make it an all day event
"""
OFFSET = "+01:00"

"""Function to filter out and store only wanted events"""
def filter_event_types(events, whiteList):
    filtered_events = []
    for event in events:
        event_data = {
            "name": event.get('name'),
            "eventType": event.get('eventType'),
            "link": event.get('link'),
            "start": event.get('start'),
            "end": event.get('end'),
            "extraData": event.get('extraData')
        }
        # Check if any whitelist phrase is in 'eventType'
        if any(phrase in event_data['eventType'] for phrase in whiteList):
            filtered_events.append(event_data)
            
    return filtered_events

"""Converts the LeekDuck json format to Google Calendar json format"""
def create_pokemon_go_event(event):
    
    startTime, endTime, all_day = all_day_event(event)
    date_status = "dateTime"
    
    # Changes date to "date" if 
    date_status = "date" if all_day else date_status
    
    event = {
            "summary": f"{event['name']}",
            "description": f"{event['link']}",
            "colorId": "3",
            "start": {
                f"{date_status}": startTime,
                "timeZone": "Europe/London",
            },
            "end": {
                f"{date_status}": endTime,
                "timeZone": "Europe/London",
            },
            "reminders": {
                "useDefault": False
            }
    }
    return event

"""Converts events that stretch to multiple days into all-day events"""
def all_day_event(event):
    
    startTime = event['start'] + OFFSET 
    endTime = event['end'] + OFFSET 
    all_day_event = False
    
    whiteList = ["event", "live-event", "pokemon-go-fest", 
                 "season", "pokemon-go-tour", "elite-raids", 
                 "raid-battles", "raid-weekend"]
    
    if any(phrase in event['eventType'] for phrase in whiteList):
        startTime = startTime.split('T')[0]
        endTime = startTime
        all_day_event = True 
        
    return startTime, endTime, all_day_event