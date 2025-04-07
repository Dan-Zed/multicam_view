"""
Tests for the CameraManager class
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from PIL import Image

from camera_manager import CameraManager

class TestCameraManager:
    """Test suite for CameraManager class."""
    
    @pytest.fixture
    def mocked_smbus(self):
        """Create a mocked SMBus for testing."""
        with patch('smbus2.SMBus') as mock_smbus:
            mock_bus = MagicMock()
            mock_smbus.return_value = mock_bus
            yield mock_bus
    
    @pytest.fixture
    def mocked_picamera(self):
        """Create a mocked Picamera2 for testing."""
        with patch('picamera2.Picamera2') as mock_picam_class:
            mock_picam = MagicMock()
            mock_picam_class.return_value = mock_picam
            
            # Mock camera info
            mock_picam.global_camera_info.return_value = [{'Model': 'imx519'}]
            
            # Mock capture_array to return a numpy array that PIL can convert
            mock_picam.capture_array.return_value = MagicMock(shape=(480, 640, 3), 
                                                            __array_interface__={
                                                                'data': (0, False),
                                                                'strides': None,
                                                                'shape': (480, 640, 3),
                                                                'typestr': '|u1',
                                                                'version': 3,
                                                            })
            
            yield mock_picam
    
    def test_initialization(self, mocked_smbus, mocked_picamera):
        """Test that CameraManager initializes correctly."""
        # This will use our mocked SMBus and Picamera2, and test_mode=True to avoid hardware access
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Initialize with the mock camera
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Check it initialized bus with the right address
        mocked_smbus.write_byte_data.assert_called_once()
        
        # Check that it started the camera
        assert mocked_picamera.start.called
        
        # Check that initial camera is 'all'
        assert cm.current_camera == 'all'
        
        # Cleanup
        cm.cleanup()
    
    def test_select_camera(self, mocked_smbus, mocked_picamera):
        """Test camera selection."""
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Set up the bus for commands
        cm.bus = mocked_smbus
        
        # Reset the mock to clear initialization calls
        mocked_smbus.reset_mock()
        
        # Test selecting camera 0
        result = cm.select_camera(0)
        assert result is True
        assert cm.current_camera == 0
        mocked_smbus.write_byte_data.assert_called_with(0x24, 0x24, 0x02)
        
        # Test broken camera 3
        mocked_smbus.reset_mock()
        result = cm.select_camera(3)
        assert result is True
        assert cm.current_camera == 3
        # Should not have called the bus for camera 3 (broken)
        assert not mocked_smbus.write_byte_data.called
        
        # Cleanup
        cm.cleanup()
    
    def test_camera_cycle(self, mocked_smbus, mocked_picamera):
        """Test camera cycling."""
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Set up the bus for commands
        cm.bus = mocked_smbus
        
        # Start cycling
        cm.start_camera_cycle(interval=0.01)  # Fast interval for testing
        assert cm.is_cycling is True
        
        # Give it time to cycle at least once
        import time
        time.sleep(0.05)
        
        # Should have selected at least one camera
        assert mocked_smbus.write_byte_data.call_count > 1
        
        # Stop cycling
        cm.stop_camera_cycle()
        assert cm.is_cycling is False
        
        # Cleanup
        cm.cleanup()
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_capture_image(self, mock_sleep, mocked_smbus, mocked_picamera):
        """Test image capture."""
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Set up the bus for commands
        cm.bus = mocked_smbus
        
        # Capture from camera 0
        mocked_picamera.reset_mock()
        image = cm.capture_image(0)
        
        # Should have reconfigured camera for still image
        assert mocked_picamera.stop.call_count == 2  # Stop and restart
        assert mocked_picamera.configure.call_count == 2  # Reconfigure twice
        assert mocked_picamera.capture_array.call_count == 1
        
        # Check image type
        assert isinstance(image, Image.Image)
        
        # Test capturing from broken camera 3
        mocked_picamera.reset_mock()
        image = cm.capture_image(3)
        
        # Should not have used the camera for camera 3
        assert not mocked_picamera.capture_array.called
        
        # Should have returned a black image with text
        assert isinstance(image, Image.Image)
        
        # Cleanup
        cm.cleanup()
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_capture_all_cameras(self, mock_sleep, mocked_smbus, mocked_picamera):
        """Test capturing from all cameras."""
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Set up the bus for commands
        cm.bus = mocked_smbus
        
        # Capture from all cameras
        images = cm.capture_all_cameras()
        
        # Should have returned 4 images
        assert len(images) == 4
        assert all(isinstance(img, Image.Image) for img in images)
        
        # Cleanup
        cm.cleanup()
    
    def test_create_grid_image(self, test_images):
        """Test grid image creation."""
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Create a grid from test images
        grid = cm.create_grid_image(test_images)
        
        # Check grid dimensions
        assert isinstance(grid, Image.Image)
        assert grid.width == test_images[0].width * 2
        assert grid.height == test_images[0].height * 2
        
        # Cleanup
        cm.cleanup()
    
    def test_add_center_cross(self, mocked_smbus, mocked_picamera):
        """Test adding center cross to image."""
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Create a test image
        image = Image.new('RGB', (640, 480), color=(100, 100, 100))
        
        # Add a cross to it
        cm._add_center_cross(image)
        
        # We can't easily check the pixels, but we can make sure it doesn't crash
        assert isinstance(image, Image.Image)
        
        # Cleanup
        cm.cleanup()
