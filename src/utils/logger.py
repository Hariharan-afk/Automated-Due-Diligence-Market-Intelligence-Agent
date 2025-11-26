import logging
import os
from logging.handlers import RotatingFileHandler
from src.config import LOGGING_CONFIG

def setup_logger(name: str, log_file: str, level=logging.INFO):
    """Function to setup as many loggers as you want"""
    
    formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    
    # Ensure logs directory exists
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding multiple handlers if logger already exists
    if not logger.handlers:
        logger.addHandler(handler)
        
        # Also log to console
        import sys
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        # Force UTF-8 for console if possible, though StreamHandler uses sys.stdout encoding by default
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except Exception:
                pass
        logger.addHandler(console_handler)
        
    return logger

def get_agent_logger(agent_name: str):
    """Get logger for agents"""
    return setup_logger(
        agent_name, 
        LOGGING_CONFIG["agents_log_file"],
        level=LOGGING_CONFIG["level"]
    )

def get_system_logger():
    """Get logger for system events"""
    return setup_logger(
        "SYSTEM", 
        LOGGING_CONFIG["system_log_file"],
        level=LOGGING_CONFIG["level"]
    )
