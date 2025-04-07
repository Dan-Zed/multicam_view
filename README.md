# MultiCam View

A web application for controlling and streaming from multiple cameras connected to a Raspberry Pi 5 via a camera multiplexer.

## Features

- Stream from four cameras at once
- Capture high-resolution images from each camera
- Switch between cameras in real-time
- Automatic camera cycling
- Create combined grid views from all cameras

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

## Development and Testing

To run the tests:

```
./run_tests.sh
```

This script will:
1. Stop any running instances of the app
2. Run the pytest test suite

## Troubleshooting

### Camera Resource Busy

If you see errors like "Failed to acquire camera: Device or resource busy", it means another process is using the camera. Stop the running application before running tests:

```
./stop.sh
```

## License

MIT License
