import logging 
from logging.handlers import RotatingFileHandler

"""Initalises up all of the logging features, ready for use"""
def configure_logging():
    # Configure the Logging
    logger = logging.getLogger('MyLogger')
    logger.setLevel(logging.INFO)

    # Add the log message handler to the logger
    handler = RotatingFileHandler('/logs', maxBytes=5*1024*1024, backupCount=3)  # 5 MB per file, keep 3 backups
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    logger.addHandler(handler)