#!/usr/bin/env python3
"""
Test script for multicam view camera functionality.

This script tests camera selection, image capture, and image generation
without needing to run the full Flask application.
"""
import os
import time
import logging
from PIL import Image
from camera_manager import CameraManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('camera_test')

# Create test directory if it doesn't exist
TEST_DIR = 'test_images'
if not os.path.exists(TEST_DIR):
    os.makedirs(TEST_DIR)

def test_camera_selection():
    """Test camera selection functionality."""
    logger.info("=== Testing Camera Selection ===")
    try:
        cm = CameraManager()
        
        # Test selecting each camera
        for i in range(cm.camera_count):
            logger.info(f"Selecting camera {i}")
            success = cm.select_camera(i)
            assert success, f"Failed to select camera {i}"
            time.sleep(1)  # Wait a second to observe
            
        # Test selecting 'all' mode
        logger.info("Selecting 'all' mode")
        success = cm.select_camera('all')
        assert success, f"Failed to select 'all' mode"
        
        logger.info("Camera selection test passed")
        return cm
    except Exception as e:
        logger.error(f"Camera selection test failed: {e}")
        raise

def test_image_capture(cm):
    """Test image capture functionality."""
    logger.info("=== Testing Image Capture ===")
    try:
        # Capture from each camera
        for i in range(cm.camera_count):
            logger.info(f"Capturing from camera {i}")
            # Skip actual capture for camera 3 (broken)
            if i == 3:
                logger.info("Skipping actual capture for broken camera 4")
                continue
                
            # Select camera and capture
            cm.select_camera(i)
            image = cm.picam.capture_array()
            pil_img = Image.fromarray(image)
            
            # Test conversion to RGB if needed
            if pil_img.mode == 'RGBA':
                pil_img = pil_img.convert('RGB')
                
            # Save test image
            filename = os.path.join(TEST_DIR, f"test_camera_{i}.jpg")
            pil_img.save(filename)
            logger.info(f"Saved test image to {filename}")
            
        logger.info("Image capture test passed")
    except Exception as e:
        logger.error(f"Image capture test failed: {e}")
        raise

def test_grid_image(cm):
    """Test grid image creation functionality."""
    logger.info("=== Testing Grid Image Creation ===")
    try:
        # Capture from all cameras
        logger.info("Capturing from all cameras")
        logger.info("Step 1: Capturing from all cameras")
        try:
            images = cm.capture_all_cameras()
            logger.info(f"Successfully captured {len(images)} images")
            assert len(images) == cm.camera_count, f"Expected {cm.camera_count} images, got {len(images)}"
        except Exception as e:
            logger.error(f"Failed to capture all camera images: {e}", exc_info=True)
            raise
        
        # Create grid image
        logger.info("Step 2: Creating grid image")
        try:
            grid = cm.create_grid_image(images)
            logger.info("Successfully created grid image")
        except Exception as e:
            logger.error(f"Failed to create grid image: {e}", exc_info=True)
            raise
        
        # Save grid image
        logger.info("Step 3: Saving grid image")
        try:
            filename = os.path.join(TEST_DIR, "test_grid.jpg")
            grid.save(filename)
            logger.info(f"Saved grid image to {filename}")
        except Exception as e:
            logger.error(f"Failed to save grid image: {e}", exc_info=True)
            raise
        
        logger.info("Grid image test passed")
    except Exception as e:
        logger.error(f"Grid image test failed: {e}")
        raise

def test_camera_cycle(cm):
    """Test camera cycling functionality."""
    logger.info("=== Testing Camera Cycling ===")
    try:
        # Start cycling
        logger.info("Starting camera cycle")
        cm.start_camera_cycle(interval=1.0)  # Fast cycling for testing
        
        # Let it cycle for a few seconds
        logger.info("Letting cameras cycle for 5 seconds...")
        time.sleep(5)
        
        # Stop cycling
        logger.info("Stopping camera cycle")
        cm.stop_camera_cycle()
        
        logger.info("Camera cycling test passed")
    except Exception as e:
        logger.error(f"Camera cycling test failed: {e}")
        raise

def run_all_tests():
    """Run all camera tests."""
    logger.info("Starting camera tests...")
    try:
        # Test camera selection
        cm = test_camera_selection()
        
        # Test image capture
        test_image_capture(cm)
        
        # Test grid image creation
        test_grid_image(cm)
        
        # Test camera cycling
        test_camera_cycle(cm)
        
        # Clean up
        cm.cleanup()
        
        logger.info("All tests passed!")
    except Exception as e:
        logger.error(f"Tests failed: {e}")
        raise

if __name__ == "__main__":
    run_all_tests()
