# Multicam View

A web-based application for viewing and capturing images from a 4-camera array on a Raspberry Pi 5.

## Features

- Live streaming from four cameras with automatic cycling
- Individual camera selection
- High-resolution image capture from all cameras
- 2x2 grid preview of captured images
- Red cross overlays for alignment
- Simple web interface accessible from any device

## Hardware Requirements

- Raspberry Pi 5
- Arducam camarray HAT with IMX519 sensors (4 cameras)
- Camera multiplexer connected to I2C bus 11 at address 0x24

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd multicam_view
   ```

2. Install system dependencies (if not already installed):
   ```
   sudo apt-get update
   sudo apt-get install -y python3-libcamera python3-picamera2 i2c-tools
   ```

3. Make sure I2C is enabled on your Raspberry Pi:
   ```
   sudo raspi-config
   ```
   Navigate to "Interface Options" > "I2C" and enable it.

4. Install Python dependencies using Poetry:
   ```
   poetry install
   ```

## Usage

1. Start the application:
   ```
   poetry run python run.py
   ```
   
   Alternatively, make it executable and run directly:
   ```
   chmod +x run.py
   ./run.py
   ```

2. Access the web interface by opening a browser and navigating to:
   ```
   http://<raspberry-pi-ip>:8000
   ```

3. Use the interface to:
   - View the live stream (cycling through cameras)
   - Select individual cameras
   - Capture high-resolution images from all cameras

## Architecture

- `camera_manager.py`: Handles camera switching, capture, and image processing
- `cam.py`: Flask web application that serves the interface and handles requests
- `run.py`: Application startup script
- `templates/index.html`: Web UI template

## Troubleshooting

- If the camera stream doesn't appear, check that:
  - All cameras are properly connected
  - I2C is enabled
  - The I2C bus and address are correct
  - You have appropriate permissions to access the camera and I2C bus

- For camera multiplexer issues, you can test directly with:
  ```
  # Select camera 0
  i2cset -y 11 0x24 0x24 0x02
  ```
