import datetime as dt 
from datetime import datetime
from tools.log_tool import get_logger

log = get_logger()

OFFSET = "+01:00"


"""Grabs extra details for community days"""
def community_day_bonuses(event):
    bonusTexts = []
    
    # Navigate to the specific structure directly
    bonuses = event.get('extraData').get('communityday', {}).get('bonuses', [])
    
    bonusTexts = [bonus['text'] for bonus in bonuses if 'text' in bonus]
    bonusTexts = '\n'.join(bonusTexts)
    
    return bonusTexts

"""Grabs extra details for spotlight hours"""
def spotlight_hour_bonuses(event):
    bonusTexts = None
    
    # Navigate to the specific structure directly
    bonuses = event.get('extraData').get('spotlight', {})
    
    # Grab the data needed
    name = bonuses.get('name')
    shiny = bonuses.get('canBeShiny')
    bonus = bonuses.get('bonus')
        
    bonusTexts = f"Pokémon: {name}\nShiny: {'✓' if shiny else '✗'}\nBonus: {bonus}"
    
    return bonusTexts

"""Grabs extra details for raids"""
def raid_bonuses(event):
    bonusTexts = None
    
    # Navigate to the specific structure directly
    bonuses = event.get('extraData').get('raidbattles', {}).get('bosses', [])
    
    # Grab the data
    for info in bonuses:
        name = info['name']
        shiny = (info['canBeShiny'])
    
    bonusTexts = f"{name} - Shiny: {'✓' if shiny else '✗'}"
    
    return bonusTexts

# Create event handler mapping
event_bonuses_handlers = {
    "community-day": community_day_bonuses,
    "pokemon-spotlight-hour": spotlight_hour_bonuses,
    "raid-battles": raid_bonuses
}

"""Function to filter out and store only wanted events"""
def filter_event_types(events, whiteList):
    filtered_events = []
    today = datetime.today().date()
    
    for event in events:
        event_data = {
            "name": event.get('name'),
            "eventType": event.get('eventType'),
            "link": event.get('link'),
            "start": event.get('start'),
            "end": event.get('end'),
            "extraData": event.get('extraData')
        }
        
        # Grab the start date and convert to comparable format
        startDate = datetime.fromisoformat(event.get('start').split('T')[0]).date()
        
        # Check if any whitelist phrase is in 'eventType' AND if the startdate is after today
        if any(phrase in event_data['eventType'] for phrase in whiteList) and startDate > today:
            filtered_events.append(event_data)
            
    return filtered_events

"""Converts the LeekDuck json format to Google Calendar json format"""
def create_pokemon_go_event(event):
    
    try: 
        startTime, endTime, allDay = all_day_event(event)
        dateStatus = "dateTime"
        bonusTexts = None
        
        # Changes date to "date" if 
        dateStatus = "date" if allDay else dateStatus
        
        # Check if there is extra data for the event
        if (event['extraData']):
            event_type = event['eventType']
            if event_type in event_bonuses_handlers:
                bonusTexts = event_bonuses_handlers[event_type](event)
        
        event = {
                "summary": f"{event['name']}",
                "description": f"<b>Extras:</b>\n{bonusTexts} \n\n{event['link']}" if bonusTexts else f"{event['link']}",
                "colorId": "3",
                "start": {
                    f"{dateStatus}": startTime,
                    "timeZone": "Europe/London",
                },
                "end": {
                    f"{dateStatus}": endTime,
                    "timeZone": "Europe/London",
                },
                "reminders": {
                    "useDefault": False
                }
        }
        
    except KeyError as e: 
        log.error(f"Could not create Pokemon Go event - {event}")
        
    return event

"""Converts events that stretch to multiple days into all-day events"""
def all_day_event(event):
    
    startTime = event['start'] + OFFSET 
    endTime = event['end'] + OFFSET 
    allDayEvent = False
    
    whiteList = ["event", "live-event", "pokemon-go-fest", 
                 "season", "pokemon-go-tour", "elite-raids", 
                 "raid-battles", "raid-weekend", "go-battle-league"]
    
    if any(phrase in event['eventType'] for phrase in whiteList):
        startTime = startTime.split('T')[0]
        endTime = startTime
        allDayEvent = True 
        
    return startTime, endTime, allDayEvent