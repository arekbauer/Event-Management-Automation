import logging, requests
from logging.handlers import RotatingFileHandler
from tools.config import DISCORD_WEBHOOK_URL
from datetime import datetime


def configure_logger():
    """Initalises up all of the logging features, ready for use"""
    # Initialise variables
    currentTime = datetime.now().strftime('%m-%d_%I%p')
    logFilePath = f"logs/{currentTime}.log"
    
    # Configure the Logging
    logger = logging.getLogger("Calendar-Script")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers
    if not logger.hasHandlers():
        # Add the log message handler to the logger
        handler = RotatingFileHandler(logFilePath, maxBytes=1*1024*1024, backupCount=3)  # 1 MB per file, keep 3 backups
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    
    return logger

def send_discord_notification(message):
    """Sends a message to the Discord webhook"""
    webhook_url = DISCORD_WEBHOOK_URL
    data = {
        "content": message,
        "embeds": [{
            "title": "Script Issue",
            "description": message,
            "color": 16711680 # red
        }]
    }
    requests.post(webhook_url, json=data, headers={'Content-Type': 'application/json'})

def get_logger():
    """Returns the configured logger"""
    return configure_logger()