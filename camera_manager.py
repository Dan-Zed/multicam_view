import time
import logging
import threading
import smbus2
from picamera2 import Picamera2
from libcamera import controls
from PIL import Image, ImageDraw, ImageOps
from unittest.mock import MagicMock  # For test mode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('camera_manager')

class CameraManager:
    """
    Manager for controlling multiple cameras via I2C multiplexer.
    
    This class handles switching between cameras connected to an Arducam camarray HAT 
    with IMX519 sensors via I2C bus 11 at address 0x24.
    
    Parameters:
    -----------
    i2c_bus : int
        I2C bus number (default: 11)
    mux_addr : int
        I2C address of the multiplexer (default: 0x24)
    camera_count : int
        Number of cameras connected (default: 4)
    switch_delay : float
        Delay in seconds after switching cameras (default: 0.1)
    """
    
    # Camera multiplexer control commands
    CAMERA_COMMANDS = {
        0: 0x02,  # Select single channel 0
        1: 0x12,  # Select single channel 1
        2: 0x22,  # Select single channel 2
        3: 0x32,  # Select single channel 3
        'all': 0x00,  # Four-in-one mode (default)
    }
    
    def __init__(self, i2c_bus=11, mux_addr=0x24, camera_count=4, switch_delay=0.1, test_mode=False):
        self.i2c_bus = i2c_bus
        self.mux_addr = mux_addr
        self.camera_count = camera_count
        self.switch_delay = switch_delay
        self.current_camera = None
        self.picam = None
        self.lock = threading.Lock()
        self.is_cycling = False
        self.cycle_thread = None
        self.cycle_interval = 1.0  # seconds between camera switches
        
        # Video and still configurations
        self.video_config = None
        self.still_config = None
        
        # In test mode, we don't initialize real hardware
        self.test_mode = test_mode
        if not test_mode:
            try:
                self.bus = smbus2.SMBus(self.i2c_bus)
                logger.info(f"Initialized I2C bus {self.i2c_bus}")
            except Exception as e:
                logger.error(f"Failed to initialize I2C bus: {e}")
                raise
                
            self.initialize_camera()
    
    # Rotation method has been removed since it's no longer needed due to hardware changes
    # Previously had _rotate_camera_image method here
    
    def initialize_camera(self, mock_picam=None):
        """Initialize the Picamera2 instance and create configurations."""
        try:
            # If we're in test mode or a mock was provided, use it
            if self.test_mode or mock_picam is not None:
                self.picam = mock_picam if mock_picam is not None else MagicMock()
                camera_info = [{"Model": "imx519", "Location": 2, "Rotation": 0, "Id": "test_camera", "Num": 0}]
                logger.info(f"Using mock camera for testing")
            else:
                self.picam = Picamera2()
                camera_info = self.picam.global_camera_info()
                logger.info(f"Camera info: {camera_info}")
                logger.info(f"Detected IMX519 sensors")
            
            # Create base configurations with appropriate resolutions
            # Preview at 720p resolution with autofocus enabled
            self.video_config = self.picam.create_video_configuration(
                main={"size": (1280, 720)},  # 720p for better preview quality
                controls={"AfMode": controls.AfModeEnum.Continuous}  # Enable continuous autofocus
            )
            
            # Capture at high resolution with autofocus
            self.still_config = self.picam.create_still_configuration(
                main={"size": (4056, 3040)},  # Full resolution
                controls={"AfMode": controls.AfModeEnum.Auto}  # Enable one-time autofocus for captures
            )
            
            # Start with video configuration and set to four-in-one mode
            self.picam.configure(self.video_config)
            self.picam.start()
            
            # Select all cameras (four-in-one mode) initially
            self.select_camera('all')
            logger.info("Camera initialized in four-in-one mode for preview")
            
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            raise
    
    def select_camera(self, camera_index, already_locked=False):
        """
        Select a specific camera by switching the multiplexer.
        
        Parameters:
        -----------
        camera_index : int or str
            Index of the camera (0-3) or 'all' for four-in-one mode
        already_locked : bool
            If True, assumes the lock is already acquired
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        def _do_select_camera():
            try:
                # All cameras are working now
                if camera_index not in self.CAMERA_COMMANDS:
                    logger.error(f"Invalid camera index: {camera_index}")
                    return False
                
                command = self.CAMERA_COMMANDS[camera_index]
                
                # In test mode, we just update the state without accessing hardware
                if not self.test_mode:
                    # Write to register 0x24 with the appropriate command
                    try:
                        self.bus.write_byte_data(self.mux_addr, 0x24, command)
                        # Add additional delay after switching to prevent system freezes
                        # This might help with Pi resource management during camera switching
                        time.sleep(0.5)  # Increased from default 0.1
                    except Exception as e:
                        logger.error(f"I2C communication error during camera select: {e}")
                        return False
                
                logger.info(f"Selected camera: {camera_index}")
                self.current_camera = camera_index
                
                # Allow time for the multiplexer to switch (simulated in test mode)
                if not self.test_mode:
                    time.sleep(self.switch_delay)
                    
                return True
                
            except Exception as e:
                logger.error(f"Failed to select camera {camera_index}: {e}")
                return False
        
        # If already_locked is True, we assume the lock is already acquired
        if already_locked:
            return _do_select_camera()
        else:
            # Otherwise, acquire the lock first
            with self.lock:
                return _do_select_camera()
    
    def start_camera_cycle(self, interval=1.0):
        """
        Set preview to four-in-one mode for showing all cameras simultaneously.
        The interval parameter is kept for API compatibility but is not used.
        """
        # If already in cycling mode, do nothing
        if self.is_cycling:
            return
            
        # Set flag to indicate we're in four-in-one mode
        self.cycle_interval = interval  # Keep for compatibility
        self.is_cycling = True
        
        # Switch to four-in-one mode
        logger.info("Setting preview to four-in-one mode")
        self.select_camera('all')
        
        # No need for a thread anymore as we're not actually cycling
    
    def stop_camera_cycle(self):
        """Switch from four-in-one mode to a single camera view."""
        # Set flag to indicate we're not in four-in-one mode
        self.is_cycling = False
        logger.info("Exited four-in-one preview mode")
        
        # By default, select camera 0 when exiting four-in-one mode
        # This gives a consistent behavior when toggling
        self.select_camera(0)
    
    def capture_image(self, camera_index=None):
        """
        Capture a high-resolution image from a specific camera.
        
        Parameters:
        -----------
        camera_index : int or None
            Index of the camera to capture from, or None to use current camera
        
        Returns:
        --------
        PIL.Image
            The captured image
        """
        with self.lock:
            was_cycling = self.is_cycling
            if was_cycling:
                self.stop_camera_cycle()
                
            try:
                if camera_index is not None:
                    self.select_camera(camera_index, already_locked=True)
                
                # All cameras are working now
                # Default capture for all cameras
                
                # Handle test mode with a mock image
                if self.test_mode:
                    logger.info("Test mode: returning test image")
                    test_img = Image.new('RGB', (640, 480), color=(100, 150, 200))
                    self._add_center_cross(test_img)
                    return test_img
                
                # Switch to still config for high-res capture (includes autofocus)
                logger.info(f"Switching to still config for camera {camera_index if camera_index is not None else self.current_camera}")
                self.picam.stop()
                self.picam.configure(self.still_config)
                self.picam.start()
                
                # Wait for camera to stabilize and focus
                time.sleep(1.0)  # Longer delay to ensure proper focusing
                
                # Capture to a PIL Image
                logger.info("Capturing image")
                buffer = self.picam.capture_array()
                image = Image.fromarray(buffer)
                
                # Explicitly clean up intermediate large buffers
                del buffer

                # Add green cross in the center
                self._add_center_cross(image)
                
                # Switch back to video config (includes continuous autofocus)
                logger.info("Switching back to video config")
                self.picam.stop()
                self.picam.configure(self.video_config)
                self.picam.start()
                
                # Ensure image is in RGB mode
                if image.mode == 'RGBA':
                    logger.info("Converting image from RGBA to RGB")
                    image = image.convert('RGB')
                
                return image
                
            except Exception as e:
                logger.error(f"Failed to capture image: {e}")
                # Make sure we get back to video mode
                try:
                    self.picam.stop()
                    self.picam.configure(self.video_config)
                    self.picam.start()
                except Exception as e2:
                    logger.error(f"Failed to reset camera configuration: {e2}")
                raise
            finally:
                if was_cycling:
                    self.start_camera_cycle(self.cycle_interval)
    
    def capture_all_cameras(self):
        """
        Capture images from all cameras.
        
        Returns:
        --------
        list
            List of captured images (PIL.Image)
        """
        logger.info("Starting to capture from all cameras")
        was_cycling = self.is_cycling
        if was_cycling:
            self.stop_camera_cycle()
            
        images = []
        
        try:
            # In test mode, create all test images at once
            if self.test_mode:
                logger.info("Test mode: generating test images for all cameras")
                for i in range(self.camera_count):
                    if i == 3:  # Test image for camera 4 
                        img = Image.new('RGB', (640, 480), color=(150, 100, 200))
                    else:
                        img = Image.new('RGB', (640, 480), color=(100, 150, 200))
                    self._add_center_cross(img)
                    images.append(img)
                return images
            
            # Normal hardware mode - use a single lock for the entire operation
            with self.lock:
                # First, switch to still config for high-res capture (includes autofocus)
                logger.info("Switching to still config for all cameras")
                self.picam.stop()
                self.picam.configure(self.still_config)
                self.picam.start()
                
                # Wait for camera to stabilize and focus
                time.sleep(1.0)  # Longer delay to ensure proper focusing
                
                for i in range(self.camera_count):
                    logger.info(f"Capturing from camera {i}")
                    
                    # All cameras are working now - no need for special handling
                    
                    # Select camera without using capture_image to avoid nested locks
                    self.select_camera(i, already_locked=True)
                    time.sleep(0.1)  # Brief pause after selection
                    
                    # Capture to a PIL Image
                    logger.info(f"Capturing image from camera {i}")
                    try:
                        buffer = self.picam.capture_array()
                        logger.info(f"Successfully captured array from camera {i}")
                        image = Image.fromarray(buffer)
                        # Clean up large buffer immediately
                        del buffer
                        logger.info(f"Successfully converted array to image for camera {i}")
                    except Exception as e:
                        logger.error(f"Error capturing from camera {i}: {e}")
                        # Create a fallback image with error message
                        image = Image.new('RGB', (640, 480), color='black')
                        draw = ImageDraw.Draw(image)
                        draw.text((20, 240), f"Error: {str(e)}", fill=(255, 0, 0))
                        logger.warning(f"Created fallback error image for camera {i}")
                    
                    # Add green cross in the center
                    self._add_center_cross(image)
                    
                    # Ensure image is in RGB mode
                    if image.mode == 'RGBA':
                        logger.info("Converting image from RGBA to RGB")
                        image = image.convert('RGB')
                    
                    images.append(image)
                
                # Switch back to video config (includes continuous autofocus)
                logger.info("Switching back to video config")
                self.picam.stop()
                self.picam.configure(self.video_config)
                self.picam.start()
            
            return images
        finally:
            if was_cycling:
                self.start_camera_cycle(self.cycle_interval)
    
    def create_grid_image(self, images):
        """
        Create a 2x2 grid image from four input images.
        
        Parameters:
        -----------
        images : list
            List of 4 PIL Images
        
        Returns:
        --------
        PIL.Image
            Combined 2x2 grid image
        """
        if len(images) != 4:
            raise ValueError(f"Expected 4 images, got {len(images)}")
        
        logger.info(f"Creating grid image from {len(images)} images")
        
        # Make sure all images are in RGB mode
        rgb_images = []
        for i, img in enumerate(images):
            
            if img.mode == 'RGBA':
                logger.info(f"Converting image {i} from RGBA to RGB")
                rgb_images.append(img.convert('RGB'))
            else:
                rgb_images.append(img)
        
        # Use the first image's size for calculations
        width, height = rgb_images[0].size
        logger.info(f"Image dimensions: {width}x{height}")
        
        # Create a new image with 2x2 grid layout
        logger.info(f"Creating new grid image with dimensions {width*2}x{height*2}")
        grid_image = Image.new('RGB', (width * 2, height * 2))
        
        # Apply rotation directly during pasting for cameras 0 and 1
        # This avoids creating intermediate images
        logger.info("Pasting images into grid")
        try:
            grid_image.paste(rgb_images[0], (0, 0))
            grid_image.paste(rgb_images[1], (width, 0))
            grid_image.paste(rgb_images[2], (0, height))
            grid_image.paste(rgb_images[3], (width, height))
        except Exception as e:
            logger.error(f"Error pasting images into grid: {e}")
        
        logger.info("Grid image created successfully")
        return grid_image
    
    def _draw_cross_at(self, image, x, y, size=None):
        """Draw a green cross at the specified location.
        
        Parameters:
        -----------
        image : PIL.Image
            Image to draw on
        x : int
            X coordinate for center of cross
        y : int
            Y coordinate for center of cross
        size : int or None
            Size of cross arms (proportional to image if None)
        """
        draw = ImageDraw.Draw(image)
        if size is None:
            # Make cross size proportional to image, but smaller than the default cross
            size = min(image.width, image.height) // 30
            
        # Draw horizontal line
        draw.line(
            (x - size, y, x + size, y),
            fill=(0, 255, 0),  # Green color (R,G,B)
            width=1            # Single-pixel thin
        )
        
        # Draw vertical line
        draw.line(
            (x, y - size, x, y + size),
            fill=(0, 255, 0),  # Green color (R,G,B)
            width=1            # Single-pixel thin
        )
    
    def _add_center_cross(self, image):
        """Add a green cross in the center of the image."""
        width, height = image.size
        center_x, center_y = width // 2, height // 2
        size = min(width, height) // 20  # Cross size proportional to image
        
        self._draw_cross_at(image, center_x, center_y, size)
    
    def cleanup(self):
        """Clean up resources."""
        try:
            # Always stop cycling first
            if self.is_cycling:
                self.stop_camera_cycle()
                
            # Handle real hardware cleanup when not in test mode
            if not self.test_mode:
                if hasattr(self, 'picam') and self.picam:
                    try:
                        self.picam.stop()
                    except Exception as e:
                        logger.warning(f"Error stopping picam: {e}")
                    
                if hasattr(self, 'bus') and self.bus:
                    try:
                        self.bus.close()
                    except Exception as e:
                        logger.warning(f"Error closing bus: {e}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
