"""
Tests for the CameraManager class
"""
import pytest
import os
import tempfile
import gc
from unittest.mock import patch, MagicMock
from PIL import Image

from camera_manager import CameraManager

class TestCameraManager:
    """Test suite for CameraManager class."""
    
    @pytest.fixture(autouse=True)
    def stop_any_camera_cycles(self):
        """Ensure any camera cycles are stopped after each test."""
        yield
        # After each test, force cleanup of any CameraManager instances that might still be running
        for obj in list(gc.get_objects()):
            if isinstance(obj, CameraManager):
                try:
                    obj.cleanup()
                except:
                    pass
    
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
        # Use test_mode=True since we can't access actual hardware during tests
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Initialize with the mock camera
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Check that bus was correctly initialized
        assert cm.i2c_bus == 1
        assert cm.mux_addr == 0x24
        
        # Check that initial camera is 'all'
        assert cm.current_camera == 'all'
        
        # Cleanup
        cm.cleanup()
    
    def test_select_camera(self, mocked_smbus, mocked_picamera):
        """Test camera selection."""
        # Use test_mode=True since we can't access actual hardware during tests
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Initialize with mock picam
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Patch the bus for testing
        cm.bus = mocked_smbus
        
        # Test selecting camera 0
        result = cm.select_camera(0)
        assert result is True
        assert cm.current_camera == 0
        
        # In test mode it shouldn't call the hardware
        assert not mocked_smbus.write_byte_data.called
        
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
        # Use test_mode=True since we can't access actual hardware during tests
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Initialize with mock picam
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Start cycling
        cm.start_camera_cycle(interval=0.01)  # Fast interval for testing
        assert cm.is_cycling is True
        
        # Give it time to cycle at least once
        import time
        time.sleep(0.05)
        
        # Just check that cycling is happening by looking at the interval
        assert cm.cycle_interval == 0.01
        
        # Stop cycling
        cm.stop_camera_cycle()
        assert cm.is_cycling is False
        
        # Cleanup
        cm.cleanup()
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_capture_image(self, mock_sleep, mocked_smbus, mocked_picamera):
        """Test image capture."""
        # Use test_mode=True since we can't access actual hardware during tests
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Initialize with mock picam
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Test capture image - in test mode, it should return a test image directly
        image = cm.capture_image(0)
        assert isinstance(image, Image.Image)
        
        # Test capturing from broken camera 3
        image = cm.capture_image(3)
        assert isinstance(image, Image.Image)
        # Should have a black color (for the broken camera)
        assert image.getpixel((0, 0))[0] == 0
        
        # Cleanup
        cm.cleanup()
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_capture_all_cameras(self, mock_sleep, mocked_smbus, mocked_picamera):
        """Test capturing from all cameras."""
        # Use test_mode=True since we can't access actual hardware during tests
        cm = CameraManager(i2c_bus=1, mux_addr=0x24, camera_count=4, test_mode=True)
        
        # Initialize with mock picam
        cm.initialize_camera(mock_picam=mocked_picamera)
        
        # Capture from all cameras
        images = cm.capture_all_cameras()
        
        # Should have returned 4 images
        assert len(images) == 4
        assert all(isinstance(img, Image.Image) for img in images)
        
        # Camera 4 (index 3) should be black (broken camera)
        assert images[3].getpixel((0, 0))[0] == 0
        
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
