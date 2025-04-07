#!/usr/bin/env python3
"""
Run all pytest tests for the multicam view application.
"""
import pytest
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_runner')

def main():
    """Run all tests."""
    logger.info("Starting multicam view tests")
    
    # Add the project root to the Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    # Run the tests
    result = pytest.main(["-v"])
    
    # Report results
    if result == 0:
        logger.info("All tests passed successfully!")
    else:
        logger.error(f"Tests failed with code {result}")
        sys.exit(result)

if __name__ == "__main__":
    main()
