# MultiCam View

A web application for controlling and streaming from multiple cameras connected to a Raspberry Pi 5 via a camera multiplexer (Arducam camarray HAT with IMX519 sensors).

## Features

- Live stream from multiple cameras via a web interface
- Capture high-resolution images (4056x3040) from each camera
- Switch between cameras in real-time
- View all cameras simultaneously in four-in-one mode
- Create combined 2x2 grid views from all cameras
- Center crosshairs on all camera views for alignment
- Debug interface for troubleshooting
- Robust error handling and memory management

## Hardware Requirements

- Raspberry Pi 5
- Arducam camarray HAT with IMX519 sensors
- Four cameras connected to the multiplexer

## Run

```
poetry run python run.py
```

## Configuration

The application uses configuration dictionaries to manage settings:

- Camera settings in `camera_manager.py`:
  - I2C bus and multiplexer address
  - Camera count and switch delay
  - Video and still resolution
  - Stabilization delay

- Application settings in `cam.py`:
  - Frame rate and cycle interval
  - Directory and file permissions
  - Error handling parameters

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

The application includes a test mode that can be enabled to simulate camera operations without requiring actual hardware.

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
3. Check the log file (`multicam.log`) for detailed error information

### Memory Issues

The application now includes explicit memory management with garbage collection at critical points. If you experience memory-related issues:

1. Review the memory usage reported in the logs during captures
2. Ensure the system has sufficient free memory
3. Consider reducing the capture resolution in the CONFIG settings

## Project Structure

- `camera_manager.py`: Core camera control functionality with memory management
- `cam.py`: Flask web application routes and endpoints
- `run.py`: Application startup script
- `templates/`: HTML templates for the web interface
- `docs/`: Project documentation and architecture details
- `captures/`: Directory for saved images
- `logs/`: Directory for log files