from tools.log_tool import get_logger, send_discord_notification
import PokemonGo, Valorant, requests, traceback, os
from tools.config import ROOT_FILE_PATH
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = os.path.join(ROOT_FILE_PATH, "json/credentials.json")

def main():
    """Main function to run the calendar scripts for Pokemon Go and Valorant."""
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

if __name__ == '__main__':
    main()