import time
import logging
import threading
import gc  # for garbage collection
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

# Basic configuration values
CONFIG = {
    "I2C_BUS": 11,
    "MUX_ADDR": 0x24,
    "CAMERA_COUNT": 4,
    "SWITCH_DELAY": 0.5,  # Delay after switching cameras (seconds)
    "STABILIZATION_DELAY": 1.0,  # Delay for camera stabilization (seconds)
    "VIDEO_RESOLUTION": (1280, 720),  # 720p for video streaming
    "STILL_RESOLUTION": (4056, 3040),  # Full resolution for still captures
    "CROP_RESOLUTION": (1775, 1160),  # Center cropped dimensions for grid composition
    "CYCLE_INTERVAL": 1.0,  # Default seconds between camera cycles
}


class CameraManager:
    """
    Manager for controlling multiple cameras via I2C multiplexer.
    
    This class handles switching between cameras connected to an Arducam camarray HAT 
    with IMX519 sensors via I2C bus. It provides functionality for camera selection,
    image capture, grid creation, and cycling between cameras.
    
    Parameters:
    -----------
    i2c_bus : int
        I2C bus number (default from CONFIG)
    mux_addr : int
        I2C address of the multiplexer (default from CONFIG)
    camera_count : int
        Number of cameras connected (default from CONFIG)
    switch_delay : float
        Delay in seconds after switching cameras (default from CONFIG)
    test_mode : bool
        If True, use mock objects instead of real hardware (default: False)
        
    Example:
    --------
    >>> cm = CameraManager()
    >>> cm.select_camera(0)  # Select first camera
    >>> image = cm.capture_image()  # Capture image from selected camera
    >>> cm.cleanup()  # Clean up resources when done
    """
    
    # Camera multiplexer control commands
    CAMERA_COMMANDS = {
        0: 0x02,  # Select single channel 0
        1: 0x12,  # Select single channel 1
        2: 0x22,  # Select single channel 2
        3: 0x32,  # Select single channel 3
        'all': 0x00,  # Four-in-one mode (default)
    }
    
    def __init__(self, i2c_bus=None, mux_addr=None, camera_count=None, 
                 switch_delay=None, test_mode=False):
        # Use provided values or defaults from CONFIG
        self.i2c_bus = i2c_bus if i2c_bus is not None else CONFIG["I2C_BUS"]
        self.mux_addr = mux_addr if mux_addr is not None else CONFIG["MUX_ADDR"]
        self.camera_count = camera_count if camera_count is not None else CONFIG["CAMERA_COUNT"]
        self.switch_delay = switch_delay if switch_delay is not None else CONFIG["SWITCH_DELAY"]
        
        self.current_camera = None
        self.picam = None
        self.lock = threading.Lock()
        self.is_cycling = False
        self.cycle_thread = None
        self.cycle_interval = CONFIG["CYCLE_INTERVAL"]
        
        # Video and still configurations
        self.video_config = None
        self.still_config = None
        
        # In test mode, we don't initialize real hardware
        self.test_mode = test_mode
        self.bus = None
        
        if not test_mode:
            try:
                self.bus = smbus2.SMBus(self.i2c_bus)
                logger.info(f"Initialized I2C bus {self.i2c_bus}")
            except Exception as e:
                logger.error(f"Failed to initialize I2C bus: {e}", exc_info=True)
                raise
                
        self.initialize_camera()
    
    def initialize_camera(self, mock_picam=None):
        """
        Initialize the Picamera2 instance and create configurations.
        
        Parameters:
        -----------
        mock_picam : MagicMock, optional
            Mock camera object for testing
            
        Returns:
        --------
        None
        
        Raises:
        -------
        Exception
            If camera initialization fails
        """
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
            # Preview at 720p resolution with autofocus enabled and white balance adjustment
            self.video_config = self.picam.create_video_configuration(
                main={"size": CONFIG["VIDEO_RESOLUTION"]},
                controls={
                    "AfMode": controls.AfModeEnum.Continuous,  # Enable continuous autofocus
                    "AwbEnable": 0,                          # Disable auto white balance
                    "ColourGains": (1, 1)                  # Apply calibrated white balance gains
                }
            )
            logger.info("Applied manual white balance: red_gain=0.9951, blue_gain=0.7410")
            
            # Capture at high resolution with autofocus and white balance adjustment
            self.still_config = self.picam.create_still_configuration(
                main={"size": CONFIG["STILL_RESOLUTION"]},
                controls={
                    "AfMode": controls.AfModeEnum.Auto,  # Enable one-time autofocus for captures
                    "AwbEnable": 0,                     # Disable auto white balance
                    "ColourGains": (0.9951, 0.7410)      # Apply calibrated white balance gains
                }
            )
            
            # Start with video configuration and set to four-in-one mode
            self.picam.configure(self.video_config)
            self.picam.start()
            
            # Select all cameras (four-in-one mode) initially
            self.select_camera('all')
            logger.info("Camera initialized in four-in-one mode for preview")
            
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}", exc_info=True)
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
                # Check if camera index is valid
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
                        time.sleep(self.switch_delay)
                    except Exception as e:
                        logger.error(f"I2C communication error during camera select: {e}", exc_info=True)
                        return False
                
                logger.info(f"Selected camera: {camera_index}")
                self.current_camera = camera_index
                return True
                
            except Exception as e:
                logger.error(f"Failed to select camera {camera_index}: {e}", exc_info=True)
                return False
        
        # If already_locked is True, we assume the lock is already acquired
        if already_locked:
            return _do_select_camera()
        else:
            # Otherwise, acquire the lock first
            with self.lock:
                return _do_select_camera()
    
    def start_camera_cycle(self, interval=None):
        """
        Set preview to four-in-one mode for showing all cameras simultaneously.
        
        Parameters:
        -----------
        interval : float, optional
            Interval between camera switches (kept for API compatibility)
            
        Returns:
        --------
        None
        """
        # If already in cycling mode, do nothing
        if self.is_cycling:
            return
            
        # Set flag to indicate we're in four-in-one mode
        self.cycle_interval = interval if interval is not None else CONFIG["CYCLE_INTERVAL"]
        self.is_cycling = True
        
        # Switch to four-in-one mode
        logger.info("Setting preview to four-in-one mode")
        self.select_camera('all')
    
    def stop_camera_cycle(self):
        """
        Switch from four-in-one mode to a single camera view.
        
        Returns:
        --------
        None
        """
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
            
        Raises:
        -------
        Exception
            If image capture fails
        """
        with self.lock:
            was_cycling = self.is_cycling
            if was_cycling:
                self.stop_camera_cycle()
                
            try:
                # Force garbage collection before capture
                gc.collect()
                
                if camera_index is not None:
                    self.select_camera(camera_index, already_locked=True)
                
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
                time.sleep(CONFIG["STABILIZATION_DELAY"])
                
                # Capture to a PIL Image
                logger.info("Capturing image")
                try:
                    buffer = self.picam.capture_array()
                    image = Image.fromarray(buffer)
                    
                    # Explicitly clean up intermediate large buffers
                    del buffer
                    gc.collect()  # Force garbage collection after using large buffer
                    
                    # Add green cross in the center
                    self._add_center_cross(image)
                    
                    # Ensure image is in RGB mode
                    if image.mode == 'RGBA':
                        logger.info("Converting image from RGBA to RGB")
                        image = image.convert('RGB')
                except Exception as capture_error:
                    logger.error(f"Error during image capture: {capture_error}", exc_info=True)
                    # Create a fallback error image
                    image = Image.new('RGB', (640, 480), color='black')
                    draw = ImageDraw.Draw(image)
                    draw.text((20, 240), f"Capture error: {str(capture_error)}", fill=(255, 0, 0))
                
                # Switch back to video config (includes continuous autofocus)
                logger.info("Switching back to video config")
                self.picam.stop()
                self.picam.configure(self.video_config)
                self.picam.start()
                
                return image
                
            except Exception as e:
                logger.error(f"Failed to capture image: {e}", exc_info=True)
                # Make sure we get back to video mode
                try:
                    self.picam.stop()
                    self.picam.configure(self.video_config)
                    self.picam.start()
                except Exception as e2:
                    logger.error(f"Failed to reset camera configuration: {e2}", exc_info=True)
                
                # Return an error image instead of raising exception
                error_img = Image.new('RGB', (640, 480), color='black')
                draw = ImageDraw.Draw(error_img)
                draw.text((20, 240), f"Error: {str(e)}", fill=(255, 0, 0))
                return error_img
            finally:
                if was_cycling:
                    self.start_camera_cycle(self.cycle_interval)
                gc.collect()  # Final garbage collection
    
    def capture_all_cameras(self):
        """
        Capture images from all cameras.
        
        Returns:
        --------
        list
            List of captured images (PIL.Image objects)
        """
        logger.info("Starting to capture from all cameras")
        was_cycling = self.is_cycling
        if was_cycling:
            self.stop_camera_cycle()
            
        images = []
        
        try:
            # Force garbage collection before starting capture sequence
            gc.collect()
            
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
                logger.info(f"Waiting for camera to stabilize ({CONFIG['STABILIZATION_DELAY']}s)")
                time.sleep(CONFIG["STABILIZATION_DELAY"])
                
                for i in range(self.camera_count):
                    logger.info(f"Capturing from camera {i}")
                    
                    # Select camera without using capture_image to avoid nested locks
                    self.select_camera(i, already_locked=True)
                    logger.info(f"Camera {i} selected, waiting for stabilization (0.5s)")
                    time.sleep(self.switch_delay)
                    
                    # Capture to a PIL Image
                    logger.info(f"Capturing image from camera {i}")
                    try:
                        # Force garbage collection before capture for memory management
                        gc.collect()
                        
                        # Capture the image
                        logger.info(f"Calling capture_array() for camera {i}")
                        buffer = self.picam.capture_array()
                        logger.info(f"Successfully captured array from camera {i} with shape: {buffer.shape}")
                        
                        # Convert to PIL Image
                        image = Image.fromarray(buffer)
                        logger.info(f"Successfully converted array to image for camera {i} with size: {image.size}")
                        
                        # Clean up large buffer immediately
                        del buffer
                        gc.collect()
                    except Exception as e:
                        logger.error(f"Error capturing from camera {i}: {e}", exc_info=True)
                        # Create a fallback image with error message
                        image = Image.new('RGB', (640, 480), color='black')
                        draw = ImageDraw.Draw(image)
                        draw.text((20, 240), f"Error: {str(e)}", fill=(255, 0, 0))
                        logger.warning(f"Created fallback error image for camera {i}")
                    
                    # Add green cross in the center
                    self._add_center_cross(image)
                    
                    # Ensure image is in RGB mode
                    if image.mode == 'RGBA':
                        logger.info(f"Converting image from camera {i} from RGBA to RGB")
                        image = image.convert('RGB')
                    
                    images.append(image)
                    logger.info(f"Successfully added image from camera {i} to images list")
                
                # Switch back to video config (includes continuous autofocus)
                logger.info("Switching back to video config")
                self.picam.stop()
                self.picam.configure(self.video_config)
                self.picam.start()
            
            logger.info(f"Successfully captured {len(images)} images")
            return images
        except Exception as e:
            logger.error(f"Unexpected error in capture_all_cameras: {e}", exc_info=True)
            # If we have an exception, try to return any images we've captured so far
            if not images:
                # If no images captured, create fallback error images for display
                for i in range(self.camera_count):
                    error_img = Image.new('RGB', (640, 480), color='black')
                    draw = ImageDraw.Draw(error_img)
                    draw.text((20, 240), f"Capture error: {str(e)}", fill=(255, 0, 0))
                    images.append(error_img)
            return images
        finally:
            # Make absolutely sure we go back to cycling if it was active before
            if was_cycling:
                logger.info("Restoring cycling mode after capture")
                self.start_camera_cycle(self.cycle_interval)
            
            # Final garbage collection to free memory
            gc.collect()
    
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
            
        Raises:
        -------
        ValueError
            If not given exactly 4 images
        Exception
            If grid creation fails
        """
        if len(images) != 4:
            raise ValueError(f"Expected 4 images, got {len(images)}")
        
        logger.info(f"Creating grid image from {len(images)} images")
        
        try:
            # Force garbage collection before grid creation
            gc.collect()
            
            # Make sure all images are in RGB mode and same size
            rgb_images = []
            for i, img in enumerate(images):
                logger.info(f"Processing image {i} with mode {img.mode} and size {img.size}")
                
                # Convert to RGB if needed
                if img.mode == 'RGBA':
                    logger.info(f"Converting image {i} from RGBA to RGB")
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    logger.info(f"Converting image {i} from {img.mode} to RGB")
                    img = img.convert('RGB')
                
                rgb_images.append(img)
            
            # Get the most common size (in case images have different sizes)
            sizes = [img.size for img in rgb_images]
            logger.info(f"Image sizes: {sizes}")
            
            # Use the first image's size as reference
            width, height = rgb_images[0].size
            logger.info(f"Using dimensions for grid: {width}x{height}")
            
            # Create a new image with 2x2 grid layout
            grid_width, grid_height = width * 2, height * 2
            logger.info(f"Creating new grid image with dimensions {grid_width}x{grid_height}")
            grid_image = Image.new('RGB', (grid_width, grid_height))
            
            # Paste images into grid, resizing if needed
            logger.info("Pasting images into grid")
            
            # Top-left image (camera 0)
            if rgb_images[0].size != (width, height):
                logger.info(f"Resizing image 0 from {rgb_images[0].size} to {width}x{height}")
                rgb_images[0] = rgb_images[0].resize((width, height))
            grid_image.paste(rgb_images[0], (0, 0))
            
            # Top-right image (camera 1)
            if rgb_images[1].size != (width, height):
                logger.info(f"Resizing image 1 from {rgb_images[1].size} to {width}x{height}")
                rgb_images[1] = rgb_images[1].resize((width, height))
            grid_image.paste(rgb_images[1], (width, 0))
            
            # Bottom-left image (camera 2)
            if rgb_images[2].size != (width, height):
                logger.info(f"Resizing image 2 from {rgb_images[2].size} to {width}x{height}")
                rgb_images[2] = rgb_images[2].resize((width, height))
            grid_image.paste(rgb_images[2], (0, height))
            
            # Bottom-right image (camera 3)
            if rgb_images[3].size != (width, height):
                logger.info(f"Resizing image 3 from {rgb_images[3].size} to {width}x{height}")
                rgb_images[3] = rgb_images[3].resize((width, height))
            grid_image.paste(rgb_images[3], (width, height))
            
            logger.info("All images pasted into grid successfully")
            
            # Force garbage collection after grid creation
            gc.collect()
            
            logger.info(f"Grid image created successfully with size {grid_image.size}")
            return grid_image
            
        except Exception as e:
            logger.error(f"Error creating grid image: {e}", exc_info=True)
            # Create a fallback grid image with error message
            fallback_img = Image.new('RGB', (1280, 960), color='black')
            draw = ImageDraw.Draw(fallback_img)
            draw.text((640, 480), f"Grid creation error: {str(e)}", fill=(255, 0, 0))
            return fallback_img
    
    def _draw_cross_at(self, image, x, y, size=None):
        """
        Draw a green cross at the specified location.
        
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
        try:
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
        except Exception as e:
            logger.error(f"Error drawing cross: {e}", exc_info=True)
            # Continue without drawing cross - non-critical feature
    
    def _add_center_cross(self, image):
        """
        Add a green cross in the center of the image.
        
        Parameters:
        -----------
        image : PIL.Image
            Image to add the cross to
        """
        try:
            width, height = image.size
            center_x, center_y = width // 2, height // 2
            size = min(width, height) // 20  # Cross size proportional to image
            
            self._draw_cross_at(image, center_x, center_y, size)
        except Exception as e:
            logger.error(f"Error adding center cross: {e}", exc_info=True)
            # Continue without adding cross - non-critical feature
            
    def center_crop_image(self, image, target_width=None, target_height=None):
        """
        Center crop an image to the specified dimensions.
        
        Parameters:
        -----------
        image : PIL.Image
            Image to crop
        target_width : int or None
            Target width for the cropped image (default from CONFIG)
        target_height : int or None
            Target height for the cropped image (default from CONFIG)
            
        Returns:
        --------
        PIL.Image
            Center cropped image
            
        Notes:
        ------
        If the target dimensions are larger than the original image,
        the original image will be returned unchanged.
        """
        try:
            # Use default from CONFIG if not specified
            if target_width is None or target_height is None:
                target_width, target_height = CONFIG["CROP_RESOLUTION"]
                
            # Get current dimensions
            orig_width, orig_height = image.size
            logger.info(f"Center cropping image from {orig_width}x{orig_height} to {target_width}x{target_height}")
            
            # If target dimensions are larger than original, return original
            if target_width >= orig_width or target_height >= orig_height:
                logger.warning(f"Target dimensions {target_width}x{target_height} are larger than original {orig_width}x{orig_height}. Not cropping.")
                return image
            
            # Calculate cropping box (left, upper, right, lower)
            left = (orig_width - target_width) // 2
            top = (orig_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            
            # Crop the image
            cropped_image = image.crop((left, top, right, bottom))
            logger.info(f"Image successfully cropped to {target_width}x{target_height}")
            
            return cropped_image
        except Exception as e:
            logger.error(f"Error center cropping image: {e}", exc_info=True)
            # Return original image in case of error
            return image
    
    def cleanup(self):
        """
        Clean up resources used by the camera manager.
        
        This method should be called when the object is no longer needed
        to ensure proper release of hardware resources.
        
        Returns:
        --------
        None
        """
        try:
            # Always stop cycling first
            if self.is_cycling:
                self.stop_camera_cycle()
                
            # Handle real hardware cleanup when not in test mode
            if not self.test_mode:
                if hasattr(self, 'picam') and self.picam:
                    try:
                        self.picam.stop()
                        logger.info("Camera stopped successfully")
                    except Exception as e:
                        logger.warning(f"Error stopping picam: {e}", exc_info=True)
                    
                if hasattr(self, 'bus') and self.bus:
                    try:
                        self.bus.close()
                        logger.info("I2C bus closed successfully")
                    except Exception as e:
                        logger.warning(f"Error closing bus: {e}", exc_info=True)
                        
            # Force final garbage collection
            gc.collect()
            logger.info("Camera manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
