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
    event = {
        "summary": f"{event['name']}",
        "description": f"{event['link']}",
        "colorId": "7",
        "start": {
            "dateTime": f"{event['start']}+01:00"
        },
        "end": {
            "dateTime": f"{event['end']}+01:00"
        },
        "reminders": {
            "useDefault": False
        }
    }
    return event