"""
pytest configuration for multicam view tests
"""
import os
import pytest
import shutil
import tempfile
from unittest.mock import patch, MagicMock
from PIL import Image

# Import the application modules we'll test
import cam
from camera_manager import CameraManager

@pytest.fixture
def app():
    """Create a Flask app test client for testing routes."""
    # Create a temporary directory for test captures
    test_dir = tempfile.mkdtemp()
    
    # Configure the app with the test directory
    cam.app.config['TESTING'] = True
    cam.app.config['CAPTURE_FOLDER'] = test_dir
    
    # Ensure the camera_manager is mocked
    old_cm = cam.camera_manager
    cam.camera_manager = None  # Will be set by mock_camera_manager fixture when needed
    
    # Return the Flask test client
    with cam.app.test_client() as client:
        # Provide the context
        yield client
        
    # Restore the original camera_manager
    cam.camera_manager = old_cm
    
    # Clean up the temp directory after the test
    shutil.rmtree(test_dir)

@pytest.fixture
def mock_camera_manager():
    """Create a mock camera manager for testing."""
    with patch('cam.CameraManager') as mock_cm_class:
        # Create a mock instance
        mock_cm = MagicMock(spec=CameraManager)
        mock_cm_class.return_value = mock_cm
        
        # Mock the current_camera property
        mock_cm.current_camera = 0
        
        # Mock capture_image to return a test image
        def mock_capture_image(camera_idx=None):
            img = Image.new('RGB', (640, 480), color=(100, 100, 100))
            return img
        
        mock_cm.capture_image.side_effect = mock_capture_image
        
        # Mock capture_all_cameras to return a list of test images
        def mock_capture_all_cameras():
            images = []
            for i in range(4):
                color = (100, 100, 100) if i != 3 else (0, 0, 0)
                img = Image.new('RGB', (640, 480), color=color)
                images.append(img)
            return images
        
        mock_cm.capture_all_cameras.side_effect = mock_capture_all_cameras
        
        # Mock create_grid_image to return a test grid
        def mock_create_grid_image(images):
            grid = Image.new('RGB', (1280, 960), color=(200, 200, 200))
            return grid
        
        mock_cm.create_grid_image.side_effect = mock_create_grid_image
        
        yield mock_cm

@pytest.fixture
def test_images():
    """Create a set of test images for testing."""
    images = []
    for i in range(4):
        color = (100, 150, 200) if i != 3 else (0, 0, 0)
        img = Image.new('RGB', (640, 480), color=color)
        images.append(img)
    return images
