#!/usr/bin/env python3
"""
Startup script for multicam view application.
"""
import logging
import os
import sys
import time
from flask import Flask
from cam import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('multicam.log')
    ]
)
logger = logging.getLogger('multicam_runner')

def main():
    """Start the multicam web application."""
    try:
        logger.info("Starting multicam view application")
        
        # Make sure captures directory exists
        captures_dir = os.path.join(os.path.dirname(__file__), 'captures')
        if not os.path.exists(captures_dir):
            os.makedirs(captures_dir)
            logger.info(f"Created captures directory: {captures_dir}")
        
        # Start the Flask app
        logger.info("Starting web server on 0.0.0.0:8000")
        app.run(host='0.0.0.0', port=8000, debug=False)
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
