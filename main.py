from tools.log_tool import get_logger
import PokemonGo, Valorant

from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = "json/credentials.json"

def main():
    log = get_logger()
    log.info("-----------------START of Calendar Script-----------------\n")
    creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, 
            scopes=SCOPES)
    
    # Run Pokemon Go Script
    PokemonGo.pokemon_go(creds=creds, delete_future_events=True)
    
    # Run Valorant Script
    Valorant.valorant(creds=creds, delete_future_events=True)
    
    log.info("-----------------END of Calendar Script-----------------")


if __name__ == '__main__':
    main()