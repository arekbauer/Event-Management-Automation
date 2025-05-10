from tools.log_tool import get_logger
from tools.config import DISCORD_WEBHOOK_URL
import PokemonGo, Valorant, requests, traceback

from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = "json/credentials.json"

def main():
    log = get_logger()
    log.info("-----------------START of Calendar Script-----------------\n")
    
    try:
        creds = service_account.Credentials.from_service_account_file(
                CREDENTIALS_PATH, 
                scopes=SCOPES)
    
        # Run Pokemon Go Script
        PokemonGo.pokemon_go(creds=creds, delete_future_events=True)
        
        # Run Valorant Script
        Valorant.valorant(creds=creds, delete_future_events=True)
        
        log.info("-----------------END of Calendar Script-----------------")

    except Exception as e:
        error_message = traceback.format_exc()
        send_discord_notification(f"Script failed with error:\n```{error_message}```")
        log.error(f"Script failed: {error_message}")
        raise # ensures script stops

def send_discord_notification(message):
    """Sends a message to the Discord webhook"""
    webhook_url = DISCORD_WEBHOOK_URL
    data = {
        "content": message,
        "embeds": [{
            "title": "Script Failure",
            "description": message,
            "color": 16711680
        }]
    }
    requests.post(webhook_url, json=data, headers={'Content-Type': 'application/json'})

if __name__ == '__main__':
    main()