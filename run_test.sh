#!/bin/bash
# First, stop any running instances of the app
echo "Stopping any running app instances..."
./stop.sh

# Wait a moment for resources to be freed
echo "Waiting for resources to free up..."
sleep 2

# Then run the tests
echo "Running tests..."
PYTHONUNBUFFERED=1 pytest -v tests/test_flask_app.py
PYTHONUNBUFFERED=1 pytest -v tests/test_camera_manager.py::TestCameraManager::test_initialization
PYTHONUNBUFFERED=1 pytest -v tests/test_camera_manager.py::TestCameraManager::test_select_camera  
PYTHONUNBUFFERED=1 pytest -v tests/test_camera_manager.py::TestCameraManager::test_camera_cycle
PYTHONUNBUFFERED=1 pytest -v tests/test_camera_manager.py::TestCameraManager::test_capture_image
PYTHONUNBUFFERED=1 pytest -v tests/test_camera_manager.py::TestCameraManager::test_capture_all_cameras
PYTHONUNBUFFERED=1 pytest -v tests/test_camera_manager.py::TestCameraManager::test_create_grid_image
PYTHONUNBUFFERED=1 pytest -v tests/test_camera_manager.py::TestCameraManager::test_add_center_cross

echo "Done!"
