import time
import logging
import threading
import smbus2
from picamera2 import Picamera2
from libcamera import controls
from PIL import Image, ImageDraw
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
            # Preview at low resolution
            self.video_config = self.picam.create_video_configuration(
                main={"size": (640, 480)}  # Low res for reliable streaming
            )
            
            # Capture at high resolution
            self.still_config = self.picam.create_still_configuration(
                main={"size": (4056, 3040)}  # Full resolution
            )
            
            # Start with video configuration
            self.picam.configure(self.video_config)
            self.picam.start()
            
            # Select all cameras initially
            self.select_camera('all')
            
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            raise
    
    def select_camera(self, camera_index):
        """
        Select a specific camera by switching the multiplexer.
        
        Parameters:
        -----------
        camera_index : int or str
            Index of the camera (0-3) or 'all' for four-in-one mode
        
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        with self.lock:
            try:
                # Special handling for camera 4 (index 3) which is broken
                if camera_index == 3:
                    logger.warning("Camera 4 (index 3) is broken, not switching to it")
                    self.current_camera = camera_index  # Still update the state
                    return True
                    
                if camera_index not in self.CAMERA_COMMANDS:
                    logger.error(f"Invalid camera index: {camera_index}")
                    return False
                
                command = self.CAMERA_COMMANDS[camera_index]
                
                # In test mode, we just update the state without accessing hardware
                if not self.test_mode:
                    # Write to register 0x24 with the appropriate command
                    self.bus.write_byte_data(self.mux_addr, 0x24, command)
                
                logger.info(f"Selected camera: {camera_index}")
                self.current_camera = camera_index
                
                # Allow time for the multiplexer to switch (simulated in test mode)
                if not self.test_mode:
                    time.sleep(self.switch_delay)
                    
                return True
                
            except Exception as e:
                logger.error(f"Failed to select camera {camera_index}: {e}")
                return False
    
    def start_camera_cycle(self, interval=1.0):
        """
        Start cycling through cameras at a specified interval.
        
        Parameters:
        -----------
        interval : float
            Time in seconds between camera switches
        """
        if self.is_cycling:
            return
            
        self.cycle_interval = interval
        self.is_cycling = True
        
        def cycle_cameras():
            camera_idx = 0
            while self.is_cycling:
                self.select_camera(camera_idx)
                time.sleep(self.cycle_interval)
                # Skip to next camera, skipping index 3 which is broken
                camera_idx = (camera_idx + 1) % self.camera_count
                if camera_idx == 3:  # Skip the broken camera
                    camera_idx = 0
        
        self.cycle_thread = threading.Thread(target=cycle_cameras)
        self.cycle_thread.daemon = True
        self.cycle_thread.start()
        logger.info(f"Started camera cycling with interval {interval}s")
    
    def stop_camera_cycle(self):
        """Stop cycling through cameras."""
        self.is_cycling = False
        if self.cycle_thread:
            self.cycle_thread.join(timeout=2.0)
            self.cycle_thread = None
        logger.info("Stopped camera cycling")
    
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
                    self.select_camera(camera_index)
                
                # Special handling for camera 4 (index 3)
                if camera_index == 3 or self.current_camera == 3:
                    logger.info("Creating dummy image for broken camera 4")
                    blank_img = Image.new('RGB', (640, 480), color='black')
                    draw = ImageDraw.Draw(blank_img)
                    text = "Camera Disconnected"
                    text_width = len(text) * 8
                    text_height = 15
                    text_x = (blank_img.width - text_width) // 2
                    text_y = (blank_img.height - text_height) // 2
                    draw.text((text_x, text_y), text, fill=(255, 0, 0))
                    self._add_center_cross(blank_img)
                    return blank_img
                
                # Handle test mode with a mock image
                if self.test_mode:
                    logger.info("Test mode: returning test image")
                    test_img = Image.new('RGB', (640, 480), color=(100, 150, 200))
                    self._add_center_cross(test_img)
                    return test_img
                
                # Switch to still config for high-res capture
                logger.info(f"Switching to still config for camera {camera_index if camera_index is not None else self.current_camera}")
                self.picam.stop()
                self.picam.configure(self.still_config)
                self.picam.start()
                
                # Wait for camera to stabilize
                time.sleep(0.5)
                
                # Capture to a PIL Image
                logger.info("Capturing image")
                buffer = self.picam.capture_array()
                image = Image.fromarray(buffer)
                
                # Add red cross in the center
                self._add_center_cross(image)
                
                # Switch back to video config
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
                except:
                    pass
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
                    if i == 3:  # Broken camera
                        img = Image.new('RGB', (640, 480), color='black')
                        draw = ImageDraw.Draw(img)
                        draw.text((240, 240), "Camera Disconnected", fill=(255, 0, 0))
                    else:
                        img = Image.new('RGB', (640, 480), color=(100, 150, 200))
                    self._add_center_cross(img)
                    images.append(img)
                return images
            
            # Normal hardware mode
            for i in range(self.camera_count):
                logger.info(f"Capturing from camera {i}")
                # Use the capture_image method which now handles the broken camera 4
                image = self.capture_image(i)
                images.append(image)
            
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
        
        # Paste images into grid
        logger.info("Pasting images into grid")
        grid_image.paste(rgb_images[0], (0, 0))
        grid_image.paste(rgb_images[1], (width, 0))
        grid_image.paste(rgb_images[2], (0, height))
        grid_image.paste(rgb_images[3], (width, height))
        
        logger.info("Grid image created successfully")
        return grid_image
    
    def _add_center_cross(self, image):
        """Add a red cross in the center of the image."""
        draw = ImageDraw.Draw(image)
        width, height = image.size
        center_x, center_y = width // 2, height // 2
        size = min(width, height) // 20  # Cross size proportional to image
        
        # Draw horizontal line
        draw.line(
            (center_x - size, center_y, center_x + size, center_y),
            fill=(255, 0, 0),
            width=3
        )
        
        # Draw vertical line
        draw.line(
            (center_x, center_y - size, center_x, center_y + size),
            fill=(255, 0, 0),
            width=3
        )
    
    def cleanup(self):
        """Clean up resources."""
        if self.is_cycling:
            self.stop_camera_cycle()
            
        if self.picam and not self.test_mode:
            self.picam.stop()
            
        if hasattr(self, 'bus') and self.bus and not self.test_mode:
            self.bus.close()
