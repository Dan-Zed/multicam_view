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
        
        # Make sure captures directory exists and is properly configured
        captures_dir = os.path.join(os.path.dirname(__file__), 'captures')
        logger.info(f"Ensuring captures directory exists: {captures_dir}")
        
        try:
            if not os.path.exists(captures_dir):
                logger.info(f"Creating captures directory: {captures_dir}")
                os.makedirs(captures_dir, exist_ok=True)
                os.chmod(captures_dir, 0o755)  # Ensure proper permissions
                logger.info(f"Created captures directory: {captures_dir}")
            else:
                logger.info(f"Captures directory already exists: {captures_dir}")
                # Still ensure permissions
                os.chmod(captures_dir, 0o755)
            
            # List directory contents
            if os.path.exists(captures_dir):
                files = os.listdir(captures_dir)
                logger.info(f"Captures directory contains {len(files)} files")
                if files:
                    logger.info(f"Sample files: {files[:5]}{'...' if len(files) > 5 else ''}")
            else:
                logger.error(f"Captures directory still does not exist after creation attempt: {captures_dir}")
        except Exception as e:
            logger.error(f"Error setting up captures directory: {e}", exc_info=True)
            # Continue anyway - we'll attempt to create it again when needed
        
        # Configure Flask app with proper capture directory
        app.config['CAPTURE_FOLDER'] = captures_dir
        
        # Start the Flask app
        logger.info("Starting web server on 0.0.0.0:8000")
        app.run(host='0.0.0.0', port=8000, debug=False)
        
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
