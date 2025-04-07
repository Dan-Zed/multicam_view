#!/bin/bash
# Stop the running webcam app first
./stop.sh

# Run the pytest tests
pytest -v
