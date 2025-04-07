# Testing the Multicam View Application

## Overview

This document explains the testing strategy and test suite for the Multicam View application.

## Test Components

The test suite consists of the following main components:

1. **Camera Manager Tests** (`tests/test_camera_manager.py`)
   - Tests for camera selection and control
   - Tests for image capture functionality
   - Tests for grid image creation
   - Tests for camera cycling

2. **Flask Application Tests** (`tests/test_flask_app.py`)
   - Tests for all HTTP endpoints
   - Tests for image capture and storage
   - Tests for debugging endpoints
   - Tests for camera control via the web interface

## Test Setup

The test suite uses pytest fixtures to set up mocks and test environments:

- `app`: Creates a Flask test client with a temporary directory for captures
- `mock_camera_manager`: Creates a mock CameraManager for testing routes
- `test_images`: Creates a set of test images for testing
- `mocked_smbus`: Mocks the SMBus for I2C communication
- `mocked_picamera`: Mocks the Picamera2 for camera operations

## Running Tests

1. Install testing dependencies:
   ```
   poetry install --with dev
   ```

2. Run the tests:
   ```
   ./run_tests.py
   ```
   
   Or use pytest directly:
   ```
   poetry run pytest
   ```

3. For coverage reports:
   ```
   poetry run pytest --cov=camera_manager --cov=cam
   ```

## Troubleshooting Tests

If tests fail, check the following:

1. **Mock Setup Issues**
   - Ensure all necessary imports are mocked correctly
   - Check that mock return values match expected formats

2. **File System Issues**
   - The tests use temporary directories for file operations
   - Check for permission issues when running tests

3. **Camera Hardware Issues**
   - Tests mock the camera hardware, but issues can occur when running on real hardware
   - Use the debugging endpoints for hardware-specific troubleshooting

## Adding New Tests

When adding new features, follow these guidelines for tests:

1. Create mocks for any new hardware or dependencies
2. Write unit tests for new functionality
3. Update the Flask application tests for any new routes
4. Ensure all tests run with both mocked hardware and real hardware (where possible)
