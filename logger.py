# loggers.py - Centralized logging configuration
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file=None, level=logging.INFO):
    """Set up a logger with file rotation"""
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    if not log_file:
        log_file = f"logs/{name}.log"

    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if not logger.handlers:
        logger.setLevel(level)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        ))
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
        
        # Console handler for development
        if os.environ.get("FLASK_ENV") != "production":
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(logging.Formatter(
                "%(name)s - %(levelname)s - %(message)s"
            ))
            logger.addHandler(console_handler)
    
    return logger

# Create global loggers
app_logger = setup_logger("app")
payments_logger = setup_logger("payments")