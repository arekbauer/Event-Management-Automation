import datetime as dt 
from datetime import datetime
from tools.log_tool import get_logger
from zoneinfo import ZoneInfo

log = get_logger()

# Needed for Daylight Saving 
OFFSET = "+01:00"


def community_day_bonuses(event: dict) -> str:
    """Grabs extra details for community days"""
    bonusTexts = []
    
    # Navigate to the specific structure directly
    bonuses = event.get('extraData').get('communityday', {}).get('bonuses', [])
    
    bonusTexts = [bonus['text'] for bonus in bonuses if 'text' in bonus]
    bonusTexts = '\n'.join(bonusTexts)
    
    return bonusTexts

def spotlight_hour_bonuses(event: dict) -> str:
    """Grabs extra details for spotlight hours"""
    bonusTexts = None
    
    # Navigate to the specific structure directly
    bonuses = event.get('extraData').get('spotlight', {})
    
    # Grab the data needed
    name = bonuses.get('name')
    shiny = bonuses.get('canBeShiny')
    bonus = bonuses.get('bonus')
        
    bonusTexts = f"Pokémon: {name}\nShiny: {'✓' if shiny else '✗'}\nBonus: {bonus}"
    
    return bonusTexts

def raid_bonuses(event: dict) -> str:
    """Grabs extra details for raids"""
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

def filter_event_types(events: dict, whiteList: list) -> list:
    """Function to filter out and store only wanted events"""
    filtered_events = []
    today = datetime.today().date()
    
    for event in events:
        # Skip events with null or missing start dates
        if not event.get('start'):
            print(f"Skipping event with null start: {event.get('name')}")
            continue
        
        try: 
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
            
            # Check if any whitelist phrase is in 'eventType' AND if the startDate is after today
            if any(phrase in event_data['eventType'] for phrase in whiteList) and startDate > today:
                filtered_events.append(event_data)
            
        except Exception as e:
            print(f"Error processing event {event.get('name')}: {e}")
            continue
        
    return filtered_events

def create_pokemon_go_event(event: dict) -> dict:
    """Converts the LeekDuck json format to Google Calendar json format"""
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
                try:    
                    bonusTexts = event_bonuses_handlers[event_type](event)
                except Exception:
                    bonusTexts = None
        
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

def all_day_event(event: dict) -> tuple[str, str, bool]:
    """Converts events that stretch to multiple days into all-day events"""
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