# MultiCam View Architecture

This document provides a detailed overview of the MultiCam View application architecture, components, design patterns, and implementation details.

## System Overview

MultiCam View is a web-based application that controls multiple cameras connected to a Raspberry Pi 5 via an Arducam camarray HAT with IMX519 sensors. The system allows users to view live streams from the cameras, switch between cameras, capture high-resolution images, and view a grid of all camera images.

### Key Components

1. **Hardware Layer**: Raspberry Pi 5, Arducam camarray HAT, four IMX519 camera sensors
2. **Camera Control Layer**: PiCamera2 API, I2C multiplexer control
3. **Application Layer**: Flask web application, camera manager
4. **Presentation Layer**: HTML/CSS/JavaScript web interface

## Component Details

### 1. Camera Manager (`camera_manager.py`)

The Camera Manager is the core component that handles all camera operations. It interacts with the hardware through the PiCamera2 API and I2C bus.

#### Key Responsibilities:

- Initialize and manage camera hardware connections
- Control camera multiplexer via I2C
- Switch between cameras
- Handle camera configuration (video vs still modes)
- Capture images from cameras
- Create combined grid images
- Manage camera cycling

#### Important Classes and Methods:

```
CameraManager
├── __init__(i2c_bus, mux_addr, camera_count, switch_delay, test_mode)
├── initialize_camera()
├── select_camera(camera_index, already_locked)
├── start_camera_cycle(interval)
├── stop_camera_cycle()
├── capture_image(camera_index)
├── capture_all_cameras()
├── create_grid_image(images)
└── cleanup()
```

#### Thread Safety:

The Camera Manager uses a threading.Lock to ensure thread-safe access to the camera hardware. The main locking strategies are:
- Lock acquisition for camera selection
- Lock acquisition for image capture
- Prevention of nested locks with the `already_locked` parameter
- Single lock acquisition for multi-camera operations

### 2. Web Application (`cam.py`)

The web application is built using Flask and provides HTTP endpoints for browser-based control of the camera system.

#### Key Routes:

- `/`: Main web interface
- `/debug`: Debug interface
- `/video_feed`: Live video stream endpoint (MJPEG stream)
- `/capture`: Endpoint to trigger image capture from all cameras
- `/latest_capture`: Gets information about the most recent capture
- `/captures/<filename>`: Serves captured images
- `/camera_info`: Returns information about the current camera setup
- `/select_camera/<camera_id>`: Endpoint to manually select a camera
- `/toggle_cycle`: Toggles automatic camera cycling
- `/debug/*`: Various debug endpoints for testing and diagnostics

#### HTTP Endpoints Pattern:

The application follows a RESTful design pattern, with endpoints returning JSON responses for API calls and HTML for browser interfaces.

### 3. Web Interface (`templates/`)

The web interface is built using HTML, CSS, and JavaScript, providing a user-friendly way to interact with the camera system.

#### Key Templates:

- `index.html`: Main user interface
- `debug_index.html`: Debug interface with additional tools and diagnostics

#### JavaScript Components:

The web interface includes JavaScript for:
- Making AJAX calls to the server
- Updating the UI with camera information
- Handling button clicks and user interactions
- Displaying status messages and errors
- Managing the capture workflow

### 4. Application Startup (`run.py`)

The main entry point for the application, responsible for:
- Configuring logging
- Creating the captures directory if it doesn't exist
- Starting the Flask web server

## Data Flow

### Live Video Stream:

1. Web browser connects to `/video_feed` endpoint
2. The `gen_frames()` function:
   - Captures frames from the current camera
   - Adds camera information and center crosshairs
   - Converts to JPEG format
   - Yields frames as an MJPEG stream
3. Browser displays the stream in an image element

### Image Capture:

1. User clicks "Capture" button in web interface
2. JavaScript makes AJAX request to `/capture` endpoint
3. Server calls `camera_manager.capture_all_cameras()`
4. Camera Manager:
   - Stops camera cycling if active
   - Switches to still configuration
   - Captures images from each camera
   - Switches back to video configuration
   - Restarts cycling if it was active
5. Server saves individual images and creates grid image
6. Server returns success/failure JSON response
7. JavaScript updates UI with the new grid image

## Design Patterns

### 1. Resource Manager Pattern

The Camera Manager follows the resource manager pattern, with proper initialization and cleanup of hardware resources:
- Acquisition of resources in `__init__`
- Release of resources in `cleanup()`
- Context managers for thread locks

### 2. Observer Pattern

The web interface observes camera state through periodic polling:
- JavaScript polls `/camera_info` endpoint
- UI updates to reflect current camera state
- Camera cycles independently of UI observation

### 3. Factory Pattern

The Camera Manager creates different types of configurations:
- Video configuration for streaming
- Still configuration for high-resolution capture

### 4. State Pattern

The camera system has different states:
- Individual camera selected
- All cameras mode
- Cycling active/inactive

## Thread Management

### Camera Cycling Thread:

- Created when `start_camera_cycle()` is called
- Runs as a daemon thread
- Cycles through cameras at specified interval
- Can be stopped via `stop_camera_cycle()`
- Uses a local reference to state variables to avoid race conditions

### Main Application Thread:

- Handles HTTP requests
- Manages camera operations
- Uses locks to synchronize with the cycling thread

## Error Handling

The application implements a multi-layered error handling approach:

1. **Hardware Level**: Catches and logs hardware communication errors
2. **Camera Manager Level**: Handles camera exceptions and provides fallbacks
3. **Web Application Level**: Catches exceptions from camera operations, returns appropriate HTTP responses
4. **Client Level**: JavaScript handles error responses and displays user-friendly messages

### Error Recovery Strategies:

- Automatic return to video mode if still capture fails
- Creation of placeholder images for broken cameras
- Graceful degradation when some but not all cameras fail
- Detailed logging for post-mortem debugging

## Configuration Management

### Camera Configurations:

- **Video Configuration**: Low resolution (640x480) for reliable streaming
- **Still Configuration**: High resolution (4056x3040) for detailed captures

### Camera Multiplexer Commands:

```
CAMERA_COMMANDS = {
    0: 0x02,    # Select single channel 0
    1: 0x12,    # Select single channel 1
    2: 0x22,    # Select single channel 2
    3: 0x32,    # Select single channel 3
    'all': 0x00, # Four-in-one mode (default)
}
```

## Testing

### Test Scripts:

- `test_camera.py`: Tests camera selection, capture, and grid creation
- `test_capture.py`: Tests capture and save functionality

### Test Mode:

The Camera Manager supports a `test_mode` parameter that allows testing without real hardware:
- Mock camera objects
- Simulated image capture
- No actual hardware communication

## Performance Considerations

### Image Processing:

- Camera switching has a configurable delay (`switch_delay`)
- High-resolution capture includes a stabilization delay
- Grid image creation operates on in-memory images

### Web Interface:

- Asynchronous AJAX requests prevent UI blocking
- Status updates provide feedback during long operations
- Throttled polling prevents excessive server load

## Security Considerations

### File System:

- Capture directory has appropriate permissions (0o755)
- Captured images have appropriate permissions (0o644)
- Input validation on file paths

### Web Security:

- No authentication currently implemented (intended for local network use)
- Input validation on API parameters
- Error responses don't expose sensitive details

## Deployment

### Running the Application:

- `start.sh`: Starts the application with Poetry
- `stop.sh`: Stops the application
- Application runs on port 8000 by default

### File Structure:

```
multicam_view/
├── camera_manager.py   # Camera control functionality
├── cam.py              # Flask application
├── run.py              # Application entry point
├── test_camera.py      # Camera test script
├── test_capture.py     # Capture test script
├── templates/          # HTML templates
│   ├── index.html      # Main interface
│   └── debug_index.html # Debug interface
├── captures/           # Directory for saved images
├── test_images/        # Directory for test images
└── docs/               # Documentation
    ├── architecture.md # This document
    └── progress_*.md   # Progress reports
```

## Customization and Extension

### Adding New Features:

1. **Camera Settings Control**: Add routes and UI for controlling camera parameters
2. **Authentication**: Add user authentication for secure access
3. **Scheduled Captures**: Implement timed capture functionality
4. **Video Recording**: Add video recording capabilities

### Modifying Camera Configurations:

Camera configurations can be modified in `camera_manager.py`:
```python
self.video_config = self.picam.create_video_configuration(
    main={"size": (640, 480)}  # Adjust resolution here
)

self.still_config = self.picam.create_still_configuration(
    main={"size": (4056, 3040)}  # Adjust resolution here
)
```

## Known Limitations

1. Camera 4 (index 3) is marked as broken in the current configuration
2. No support for camera parameter adjustments through the UI
3. No authentication mechanism for secure access
4. Limited error recovery for hardware failures
5. Not designed for high-framerate video streaming

## Troubleshooting Guide

### Common Issues:

1. **"Device or resource busy" error**: 
   - Another process is using the camera
   - Solution: Run `./stop.sh` before starting tests or the application

2. **Camera not detected**:
   - I2C connection issue
   - Solution: Check camera connections and I2C address

3. **Capture fails**:
   - May be a timing issue
   - Solution: Use the debug interface to test each component separately

4. **Slow performance**:
   - High-resolution captures take time
   - Solution: Reduce capture resolution in camera configurations

## Appendix: I2C Communication

The camera multiplexer is controlled via I2C commands:

1. Open I2C bus 11: `self.bus = smbus2.SMBus(self.i2c_bus)`
2. Select camera by writing to register 0x24: `self.bus.write_byte_data(self.mux_addr, 0x24, command)`
3. Commands are defined in `CAMERA_COMMANDS` dictionary

The I2C address of the multiplexer is configurable (default: 0x24).
