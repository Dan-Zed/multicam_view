from flask import Flask, render_template, Response, jsonify, send_from_directory
import io
import os
import time
import logging
from PIL import Image, ImageDraw
from camera_manager import CameraManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('multicam_app')

app = Flask(__name__)
app.config['CAPTURE_FOLDER'] = 'captures'

# Create captures directory if it doesn't exist
if not os.path.exists(app.config['CAPTURE_FOLDER']):
    os.makedirs(app.config['CAPTURE_FOLDER'])

# Initialize camera manager
try:
    camera_manager = CameraManager(
        i2c_bus=11,
        mux_addr=0x24,
        camera_count=4,
        switch_delay=0.1
    )
    # Start cycling through cameras every 2 seconds
    camera_manager.start_camera_cycle(interval=2.0)
except Exception as e:
    logger.error(f"Failed to initialize camera manager: {e}")
    camera_manager = None

def get_next_capture_number():
    """Get the next capture number for sequential file naming."""
    existing_files = [f for f in os.listdir(app.config['CAPTURE_FOLDER']) 
                     if f.startswith('capture_') and f.endswith('.jpg')]
    numbers = [int(f.split('_')[1].split('.')[0]) for f in existing_files 
              if f.split('_')[1].split('.')[0].isdigit()]
    return max(numbers, default=0) + 1

def gen_frames():
    """Generate frames for the video feed."""
    if not camera_manager:
        # If camera manager failed to initialize, return a blank frame
        blank_img = Image.new('RGB', (640, 480), color='black')
        draw = ImageDraw.Draw(blank_img)
        draw.text((320, 240), "Camera Error", fill=(255, 0, 0))
        img_io = io.BytesIO()
        blank_img.save(img_io, format='JPEG')
        img_io.seek(0)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + img_io.getvalue() + b'\r\n')
        return

    while True:
        try:
            # Capture a frame with the current camera
            buffer = camera_manager.picam.capture_array()
            img = Image.fromarray(buffer)
            
            # Add camera index indicator
            draw = ImageDraw.Draw(img)
            current_cam = camera_manager.current_camera
            if isinstance(current_cam, int):  # Skip for 'all' mode
                draw.text((20, 20), f"Camera {current_cam + 1}", fill=(255, 255, 255))
            
            # Add center cross
            camera_manager._add_center_cross(img)
            
            # Convert to JPEG bytes (ensuring RGB mode)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img_io = io.BytesIO()
            img.save(img_io, format='JPEG')
            img_io.seek(0)
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + img_io.getvalue() + b'\r\n')
            
            # Sleep briefly to control frame rate
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error generating frame: {e}")
            time.sleep(0.5)

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html', camera_count=4)

@app.route('/video_feed')
def video_feed():
    """Stream video feed from the cameras."""
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture')
def capture():
    """Capture images from all cameras."""
    if not camera_manager:
        return jsonify({'success': False, 'error': 'Camera manager not initialized'}), 500
        
    try:
        n = get_next_capture_number()
        
        # Capture from all cameras
        images = camera_manager.capture_all_cameras()
        
        # Save individual images
        filenames = []
        for i, img in enumerate(images):
            filename = f'capture_{n}_cam{i}.jpg'
            filepath = os.path.join(app.config['CAPTURE_FOLDER'], filename)
            img.save(filepath)
            filenames.append(filename)
            logger.info(f"Saved capture from camera {i} to {filepath}")
        
        # Create and save combined grid image
        grid_img = camera_manager.create_grid_image(images)
        grid_filename = f'capture_{n}_grid.jpg'
        grid_filepath = os.path.join(app.config['CAPTURE_FOLDER'], grid_filename)
        grid_img.save(grid_filepath)
        logger.info(f"Saved combined grid image to {grid_filepath}")
        
        return jsonify({
            'success': True, 
            'filenames': filenames,
            'grid_filename': grid_filename
        })
        
    except Exception as e:
        logger.error(f"Error during capture: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/latest_capture')
def latest_capture():
    """Get the latest capture's grid image filename."""
    try:
        grid_files = [f for f in os.listdir(app.config['CAPTURE_FOLDER']) 
                     if f.startswith('capture_') and f.endswith('_grid.jpg')]
        
        if not grid_files:
            return jsonify({'success': False, 'error': 'No captures found'}), 404
            
        # Get the latest grid file based on capture number
        latest = max(grid_files, key=lambda x: int(x.split('_')[1]))
        
        return jsonify({'success': True, 'filename': latest})
    except Exception as e:
        logger.error(f"Error getting latest capture: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/captures/<path:filename>')
def serve_capture(filename):
    """Serve capture images."""
    return send_from_directory(app.config['CAPTURE_FOLDER'], filename)

@app.route('/camera_info')
def camera_info():
    """Get information about the current camera setup."""
    if not camera_manager:
        return jsonify({
            'success': False,
            'error': 'Camera manager not initialized'
        }), 500
        
    return jsonify({
        'success': True,
        'camera_count': camera_manager.camera_count,
        'current_camera': camera_manager.current_camera,
        'cycling': camera_manager.is_cycling,
        'cycle_interval': camera_manager.cycle_interval
    })

@app.route('/select_camera/<int:camera_id>')
def select_camera(camera_id):
    """Manually select a specific camera."""
    if not camera_manager:
        return jsonify({'success': False, 'error': 'Camera manager not initialized'}), 500
        
    try:
        # Stop cycling if it's active
        was_cycling = camera_manager.is_cycling
        if was_cycling:
            camera_manager.stop_camera_cycle()
        
        # Select the specified camera
        result = camera_manager.select_camera(camera_id)
        
        if not result:
            return jsonify({'success': False, 'error': f'Failed to select camera {camera_id}'}), 500
            
        return jsonify({
            'success': True,
            'camera': camera_id,
            'was_cycling': was_cycling
        })
    except Exception as e:
        logger.error(f"Error selecting camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/toggle_cycle')
def toggle_cycle():
    """Toggle camera cycling on/off."""
    if not camera_manager:
        return jsonify({'success': False, 'error': 'Camera manager not initialized'}), 500
        
    try:
        if camera_manager.is_cycling:
            camera_manager.stop_camera_cycle()
            status = 'stopped'
        else:
            camera_manager.start_camera_cycle()
            status = 'started'
            
        return jsonify({
            'success': True,
            'cycling': camera_manager.is_cycling,
            'status': status
        })
    except Exception as e:
        logger.error(f"Error toggling camera cycle: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
