# MultiCam View

A web application for controlling and streaming from multiple cameras connected to a Raspberry Pi 5 via a camera multiplexer (Arducam camarray HAT with IMX519 sensors).

## Features

- Live stream from multiple cameras via a web interface
- Capture high-resolution images (4056x3040) from each camera
- Switch between cameras in real-time
- Automatic camera cycling at configurable intervals
- Create combined 2x2 grid views from all cameras
- Center crosshairs on all camera views for alignment
- Debug interface for troubleshooting

## Hardware Requirements

- Raspberry Pi 5
- Arducam camarray HAT with IMX519 sensors
- Four cameras connected to the multiplexer (supports three functional cameras in current config)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/multicam_view.git
   cd multicam_view
   ```

2. Install dependencies with Poetry:
   ```
   poetry install
   ```

3. Run the application:
   ```
   ./start.sh
   ```

4. Access the web interface at:
   ```
   http://[raspberry-pi-ip]:8000/
   ```

5. For debugging and troubleshooting, access the debug interface:
   ```
   http://[raspberry-pi-ip]:8000/debug
   ```

## Development and Testing

To run the tests:

```
./run_tests.sh
```

This script will:
1. Stop any running instances of the app
2. Run the pytest test suite

Alternatively, you can run individual tests with Poetry:

```
poetry run python test_camera.py  # Test camera functionality
poetry run python test_capture.py  # Test capture functionality
```

## Troubleshooting

### Camera Resource Busy

If you see errors like "Failed to acquire camera: Device or resource busy", it means another process is using the camera. Stop the running application before running tests:

```
./stop.sh
```

### Capture Issues

If camera capture isn't working:

1. Check the debug interface at `/debug`
2. Use the test buttons to diagnose issues:
   - "Test Camera API" to verify camera connectivity
   - "Test Captures Dir" to check directory permissions
   - "Test Capture API" to verify single camera capture
   - "Test Full Pipeline" to test the entire capture process

### Camera Configuration

The system is configured for:
- Low-resolution (640x480) streaming for the live view
- High-resolution (4056x3040) capture when taking photos
- Camera 4 (index 3) is marked as broken in the current configuration

## Project Structure

- `camera_manager.py`: Core camera control functionality
- `cam.py`: Flask web application routes
- `run.py`: Application startup script
- `templates/`: HTML templates for the web interface
- `docs/`: Project documentation and progress reports
- `test_*.py`: Test scripts for different components

## License

MIT License
