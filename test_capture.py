#!/usr/bin/env python3
"""
Simple test script to capture and save images from all cameras.
This helps verify that file saving and directory permissions are working correctly.
"""
import os
import logging
import sys
from camera_manager import CameraManager

# Configure logging to show more details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('test_capture')

# Directory for test captures
TEST_DIR = 'test_captures'
if not os.path.exists(TEST_DIR):
    os.makedirs(TEST_DIR)
    logger.info(f"Created test directory: {TEST_DIR}")
    
    # Set directory permissions
    try:
        os.chmod(TEST_DIR, 0o755)
        logger.info("Set permissions on test directory")
    except Exception as e:
        logger.warning(f"Could not set permissions: {e}")

def test_capture_and_save():
    """Test capturing from all cameras and saving the files."""
    try:
        logger.info("Initializing camera manager")
        cm = CameraManager()
        
        logger.info("Capturing images from all cameras")
        images = cm.capture_all_cameras()
        logger.info(f"Successfully captured {len(images)} images")
        
        # Save individual images
        for i, img in enumerate(images):
            filename = f'test_capture_cam{i}.jpg'
            filepath = os.path.join(TEST_DIR, filename)
            logger.info(f"Saving image from camera {i} to {filepath}")
            
            # Ensure image is RGB
            if img.mode == 'RGBA':
                logger.info(f"Converting image {i} from RGBA to RGB")
                img = img.convert('RGB')
                
            img.save(filepath)
            
            # Set file permissions
            try:
                os.chmod(filepath, 0o644)
                logger.info(f"Set permissions on {filepath}")
            except Exception as e:
                logger.warning(f"Could not set permissions on {filepath}: {e}")
        
        # Create and save grid image
        logger.info("Creating grid image")
        grid_img = cm.create_grid_image(images)
        grid_filepath = os.path.join(TEST_DIR, 'test_grid.jpg')
        logger.info(f"Saving grid image to {grid_filepath}")
        grid_img.save(grid_filepath)
        
        # Set file permissions
        try:
            os.chmod(grid_filepath, 0o644)
            logger.info(f"Set permissions on {grid_filepath}")
        except Exception as e:
            logger.warning(f"Could not set permissions on {grid_filepath}: {e}")
            
        logger.info("Test completed successfully!")
        
        # Show file sizes to ensure they were saved properly
        for filename in os.listdir(TEST_DIR):
            filepath = os.path.join(TEST_DIR, filename)
            size = os.path.getsize(filepath)
            logger.info(f"File: {filename}, Size: {size} bytes")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        if 'cm' in locals():
            cm.cleanup()

if __name__ == "__main__":
    test_capture_and_save()
