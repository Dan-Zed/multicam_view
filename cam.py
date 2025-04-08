from flask import Flask, render_template, Response, jsonify, send_from_directory
import io
import os
import time
import logging
import traceback
import gc  # for garbage collection
import psutil  # for memory monitoring - you may need to install this with pip/poetry
from PIL import Image, ImageDraw
from camera_manager import CameraManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('multicam_app')

app = Flask(__name__)

# Use absolute path for captures folder
captures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures')
app.config['CAPTURE_FOLDER'] = captures_dir
logger.info(f"Using captures directory: {captures_dir}")

# Create captures directory if it doesn't exist
if not os.path.exists(app.config['CAPTURE_FOLDER']):
    logger.info(f"Creating captures directory: {app.config['CAPTURE_FOLDER']}")
    os.makedirs(app.config['CAPTURE_FOLDER'])
    # Ensure directory is accessible
    try:
        os.chmod(app.config['CAPTURE_FOLDER'], 0o755)
        logger.info(f"Set permissions on captures directory")
    except Exception as e:
        logger.warning(f"Could not set permissions on captures directory: {e}")
else:
    logger.info(f"Captures directory exists: {app.config['CAPTURE_FOLDER']}")

# Initialize camera manager
try:
    camera_manager = CameraManager(
        i2c_bus=11,
        mux_addr=0x24,
        camera_count=4,
        switch_delay=0.5  # Increased from 0.1 to allow more time for switching
    )
    # Start cycling through cameras every 2 seconds (default)
    camera_manager.start_camera_cycle(interval=2.0)
except Exception as e:
    logger.error(f"Failed to initialize camera manager: {e}")
    camera_manager = None

def get_next_capture_number():
    """Get the next capture number for sequential file naming."""
    try:
        existing_files = [f for f in os.listdir(app.config['CAPTURE_FOLDER']) 
                        if f.startswith('capture_') and f.endswith('.jpg')]
        logger.info(f"Found {len(existing_files)} existing capture files")
        
        # Get capture numbers from both grid and individual files
        numbers = []
        for f in existing_files:
            parts = f.split('_')
            if len(parts) >= 2 and parts[1].split('.')[0].isdigit():
                numbers.append(int(parts[1].split('.')[0]))
            elif len(parts) >= 2 and '_cam' in f and parts[1].isdigit():
                numbers.append(int(parts[1]))
        
        next_num = max(numbers, default=0) + 1
        logger.info(f"Next capture number will be: {next_num}")
        return next_num
    except Exception as e:
        logger.error(f"Error getting next capture number: {e}", exc_info=True)
        # Fallback to timestamp if there's an error
        return int(time.time())

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

    # Initialize frame tracking
    if not hasattr(gen_frames, 'frame_count'):
        gen_frames.frame_count = 0
        gen_frames.last_frame_time = time.time()

    while True:
        try:
            # Capture a frame with the current camera
            buffer = camera_manager.picam.capture_array()
            img = Image.fromarray(buffer)
            
            # Add camera index indicator and center crosses
            draw = ImageDraw.Draw(img)
            current_cam = camera_manager.current_camera
            
            if isinstance(current_cam, int):  # Single camera mode
                # Add camera number indicator
                draw.text((20, 20), f"Camera {current_cam + 1}", fill=(255, 255, 255))
                
                # Add center cross for single camera view
                camera_manager._add_center_cross(img)
            else:  # Four-in-one mode - add crosses to each quadrant
                # Get dimensions for calculating quadrant centers
                width, height = img.size
                quadrant_width = width // 2
                quadrant_height = height // 2
                
                # Add a cross to the center of each quadrant
                # Top-left quadrant
                camera_manager._draw_cross_at(img, quadrant_width // 2, quadrant_height // 2)
                
                # Top-right quadrant
                camera_manager._draw_cross_at(img, quadrant_width + quadrant_width // 2, quadrant_height // 2)
                
                # Bottom-left quadrant
                camera_manager._draw_cross_at(img, quadrant_width // 2, quadrant_height + quadrant_height // 2)
                
                # Bottom-right quadrant
                camera_manager._draw_cross_at(img, quadrant_width + quadrant_width // 2, quadrant_height + quadrant_height // 2)
            
            # Rotation removed - hardware changes make it unnecessary
            # (previously had rotation code here for cameras 0 and 1)
            
            # Convert to JPEG bytes (ensuring RGB mode)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img_io = io.BytesIO()
            img.save(img_io, format='JPEG')
            img_io.seek(0)
            
            # Update frame counter
            if not hasattr(gen_frames, 'frame_count'):
                gen_frames.frame_count = 1
                gen_frames.last_frame_time = time.time()
            else:
                gen_frames.frame_count += 1

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + img_io.getvalue() + b'\r\n')
            
            # Explicitly clean up to prevent memory leaks
            del buffer
            del img
            del img_io
            
            # Sleep briefly to control frame rate and reduce CPU usage
            time.sleep(0.1)  # Back to default - 10 fps
            
            # Periodically check if we need to restart the camera
            if hasattr(gen_frames, 'frame_count') and gen_frames.frame_count % 100 == 0:
                if time.time() - gen_frames.last_frame_time > 5.0:  # If more than 5 seconds between frames
                    logger.warning("Detected potential camera freeze - no restart logic implemented")
                    # Example restart code (commented out to avoid syntax issues):
                    # camera_manager = CameraManager(
                    #     i2c_bus=11,
                    #     mux_addr=0x24,
                    #     camera_count=4,
                    #     switch_delay=0.5
                    # )
                    # camera_manager.start_camera_cycle(interval=2.0)
            
            # Update last frame time
            gen_frames.last_frame_time = time.time()
            
        except Exception as e:
            logger.error(f"Error generating frame: {e}")
            # Return an error frame instead of just logging
            try:
                error_img = Image.new('RGB', (640, 480), color='black')
                draw = ImageDraw.Draw(error_img)
                draw.text((320, 240), f"Frame Error: {str(e)}", fill=(255, 0, 0))
                img_io = io.BytesIO()
                error_img.save(img_io, format='JPEG')
                img_io.seek(0)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + img_io.getvalue() + b'\r\n')
            except Exception as e2:
                logger.error(f"Error creating error frame: {e2}")
            time.sleep(1.0)  # Longer sleep on error

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
        logger.error("Cannot capture: camera manager not initialized")
        return jsonify({'success': False, 'error': 'Camera manager not initialized'}), 500
        
    try:
        logger.info("==== Starting capture from all cameras ====")
        
        # Force GC to free up memory before capture
        gc.collect()
        memory_before = psutil.Process().memory_info().rss / (1024 * 1024)  # MB
        logger.info(f"Memory usage before capture: {memory_before:.2f} MB")
        
        # Get next capture number
        n = get_next_capture_number()
        logger.info(f"Using capture number {n}")
        
        # Check and ensure capture directory exists
        capture_dir = app.config['CAPTURE_FOLDER']
        logger.info(f"Checking capture directory: {capture_dir}")
        if not os.path.exists(capture_dir):
            logger.warning(f"Capture directory {capture_dir} does not exist, creating it")
            os.makedirs(capture_dir, exist_ok=True)
            try:
                os.chmod(capture_dir, 0o755)
                logger.info(f"Set permissions on capture directory {capture_dir}")
            except Exception as e:
                logger.warning(f"Could not set permissions on {capture_dir}: {e}")
        
        # Capture from all cameras
        logger.info("Capturing images from all cameras")
        try:
            images = camera_manager.capture_all_cameras()
            logger.info(f"Successfully captured {len(images)} images with dimensions: {[img.size for img in images]}")
        except Exception as e:
            logger.error(f"Failed to capture all camera images: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'Image capture failed: {str(e)}'}), 500
        
        # Save individual images
        filenames = []
        for i, img in enumerate(images):
            filename = f'capture_{n}_cam{i}.jpg'
            filepath = os.path.join(capture_dir, filename)
            logger.info(f"Saving image from camera {i} to {filepath}")
            try:
                # Ensure image is in RGB mode for JPEG
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Save the image
                img.save(filepath)
                
                # Verify the file was created
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath)
                    logger.info(f"Verified file saved: {filepath} ({file_size} bytes)")
                    
                    # Ensure file permissions
                    try:
                        os.chmod(filepath, 0o644)
                    except Exception as e:
                        logger.warning(f"Could not set permissions on {filepath}: {e}")
                    
                    filenames.append(filename)
                else:
                    logger.error(f"File not found after save: {filepath}")
            except Exception as e:
                logger.error(f"Failed to save image from camera {i}: {e}", exc_info=True)
                # We'll continue to try saving other images
        
        if not filenames:
            logger.error("Failed to save any images")
            return jsonify({'success': False, 'error': 'Failed to save any images'}), 500
        
        # Create and save combined grid image
        logger.info("Creating grid image")
        try:
            grid_img = camera_manager.create_grid_image(images)
            grid_filename = f'capture_{n}_grid.jpg'
            grid_filepath = os.path.join(capture_dir, grid_filename)
            logger.info(f"Saving grid image to {grid_filepath}")
            
            # Ensure grid image is in RGB mode
            if grid_img.mode == 'RGBA':
                grid_img = grid_img.convert('RGB')
                
            grid_img.save(grid_filepath)
            
            # Verify the grid file was created
            if os.path.exists(grid_filepath):
                grid_file_size = os.path.getsize(grid_filepath)
                logger.info(f"Verified grid file saved: {grid_filepath} ({grid_file_size} bytes)")
                
                # Ensure file permissions
                try:
                    os.chmod(grid_filepath, 0o644)
                except Exception as e:
                    logger.warning(f"Could not set permissions on {grid_filepath}: {e}")
            else:
                logger.error(f"Grid file not found after save: {grid_filepath}")
                grid_filename = None
        except Exception as e:
            logger.error(f"Failed to create or save grid image: {e}", exc_info=True)
            grid_filename = None
            # We'll still return the individual images if they were saved
        
        # List the contents of the captures directory to verify
        try:
            dir_contents = os.listdir(capture_dir)
            logger.info(f"Captures directory now contains {len(dir_contents)} files")
            # Check if our new files are in the directory
            new_files = [f for f in dir_contents if f'capture_{n}' in f]
            logger.info(f"New files created: {new_files}")
        except Exception as e:
            logger.error(f"Error listing directory contents: {e}")
        
        # Force GC again and check memory usage
        gc.collect()
        memory_after = psutil.Process().memory_info().rss / (1024 * 1024)  # MB
        logger.info(f"Memory usage after capture: {memory_after:.2f} MB (change: {memory_after - memory_before:.2f} MB)")
        
        logger.info("==== Capture process completed successfully ====")
        return jsonify({
            'success': True, 
            'filenames': filenames,
            'grid_filename': grid_filename,
            'capture_number': n
        })
        
    except Exception as e:
        logger.error(f"Unhandled error during capture: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/latest_capture')
def latest_capture():
    """Get the latest capture's grid image filename."""
    try:
        logger.info("Looking for latest capture")
        captures_folder = app.config['CAPTURE_FOLDER']
        logger.info(f"Scanning captures folder: {captures_folder}")
        
        # Check if directory exists first
        if not os.path.exists(captures_folder):
            logger.warning(f"Captures directory does not exist: {captures_folder}")
            return jsonify({'success': False, 'error': 'Captures directory not found'}), 404
            
        # Get all grid files
        try:
            all_files = os.listdir(captures_folder)
            grid_files = [f for f in all_files 
                        if f.startswith('capture_') and '_grid.jpg' in f]
            
            logger.info(f"Found {len(grid_files)} grid files out of {len(all_files)} total files")
        except Exception as e:
            logger.error(f"Error listing captures directory: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'Error listing directory: {str(e)}'}), 500
        
        if not grid_files:
            logger.warning("No grid captures found")
            return jsonify({'success': False, 'error': 'No captures found'}), 404
            
        # Get the latest grid file based on capture number
        try:
            capture_numbers = []
            for f in grid_files:
                parts = f.split('_')
                if len(parts) >= 2 and parts[1].isdigit():
                    capture_numbers.append((int(parts[1]), f))
            
            if not capture_numbers:
                logger.warning("No valid capture numbers found in filenames")
                # Fallback to alphabetical sort if we can't extract numbers
                latest = sorted(grid_files)[-1]
            else:
                # Sort by capture number (first tuple element)
                capture_numbers.sort(reverse=True)
                # Get the filename (second tuple element)
                latest = capture_numbers[0][1]
                
            logger.info(f"Latest grid capture: {latest}")
            
            # Verify the file exists and is readable
            filepath = os.path.join(captures_folder, latest)
            if not os.path.exists(filepath):
                logger.error(f"Found latest capture filename {latest}, but file does not exist at {filepath}")
                return jsonify({'success': False, 'error': 'Latest capture file not found'}), 404
                
            # Get basic file info for logging
            file_size = os.path.getsize(filepath)
            logger.info(f"Latest capture file size: {file_size} bytes")
            
            return jsonify({
                'success': True, 
                'filename': latest,
                'file_size': file_size,
                'full_path': filepath
            })
        except Exception as e:
            logger.error(f"Error parsing capture filenames: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'Error parsing filenames: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error getting latest capture: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/captures/<path:filename>')
def serve_capture(filename):
    """Serve capture images."""
    logger.info(f"Request to serve capture file: {filename}")
    try:
        return send_from_directory(app.config['CAPTURE_FOLDER'], filename)
    except Exception as e:
        logger.error(f"Error serving capture file {filename}: {e}")
        return jsonify({'error': 'File not found'}), 404

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

@app.route('/debug/captures')
def debug_captures():
    """Debug route to list captures directory contents."""
    try:
        capture_dir = app.config['CAPTURE_FOLDER']
        logger.info(f"Listing contents of {capture_dir}")
        
        # Get directory contents
        if not os.path.exists(capture_dir):
            return jsonify({
                'error': f"Directory {capture_dir} does not exist",
                'success': False
            })
            
        files = os.listdir(capture_dir)
        file_info = []
        
        for filename in files:
            filepath = os.path.join(capture_dir, filename)
            try:
                stat_info = os.stat(filepath)
                file_info.append({
                    'name': filename,
                    'size': stat_info.st_size,
                    'modified': time.ctime(stat_info.st_mtime),
                    'permissions': oct(stat_info.st_mode)[-3:]
                })
            except Exception as e:
                file_info.append({
                    'name': filename,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'directory': capture_dir,
            'file_count': len(files),
            'files': file_info
        })
        
    except Exception as e:
        logger.error(f"Error in debug captures route: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug/test_capture')
def debug_test_capture():
    """Debug route to test capturing and saving a single image."""
    if not camera_manager:
        return jsonify({'success': False, 'error': 'Camera manager not initialized'}), 500
        
    try:
        logger.info("Test capture: capturing from camera 0")
        img = camera_manager.capture_image(0)
        
        # Save test image
        test_filename = f'test_capture_{int(time.time())}.jpg'
        test_filepath = os.path.join(app.config['CAPTURE_FOLDER'], test_filename)
        
        logger.info(f"Test capture: saving to {test_filepath}")
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        img.save(test_filepath)
        
        # Get file info
        stat_info = os.stat(test_filepath)
        file_info = {
            'filename': test_filename,
            'path': test_filepath,
            'size': stat_info.st_size,
            'modified': time.ctime(stat_info.st_mtime)
        }
        
        return jsonify({
            'success': True,
            'message': 'Test capture successful',
            'file': file_info
        })
        
    except Exception as e:
        logger.error(f"Error in test capture: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug/test_capture_pipeline')
def debug_test_capture_pipeline():
    """Debug route to test the entire capture pipeline."""
    if not camera_manager:
        return jsonify({'success': False, 'error': 'Camera manager not initialized'}), 500
        
    try:
        # Step 1: Check capture directory
        capture_dir = app.config['CAPTURE_FOLDER']
        capture_dir_info = {
            'path': capture_dir,
            'exists': os.path.exists(capture_dir),
            'is_dir': os.path.isdir(capture_dir) if os.path.exists(capture_dir) else False,
            'permissions': oct(os.stat(capture_dir).st_mode)[-3:] if os.path.exists(capture_dir) else None,
            'writable': os.access(capture_dir, os.W_OK) if os.path.exists(capture_dir) else False
        }
        
        # Step 2: Test image capture from a single camera
        logger.info("Test pipeline: capturing image from camera 0")
        img = camera_manager.capture_image(0)
        
        # Step 3: Test saving image to disk
        test_filename = f'test_pipeline_{int(time.time())}.jpg'
        test_filepath = os.path.join(capture_dir, test_filename)
        logger.info(f"Test pipeline: saving image to {test_filepath}")
        
        if img.mode == 'RGBA':
            img = img.convert('RGB')
            
        img.save(test_filepath)
        
        # Step 4: Check that the file was saved successfully
        file_info = {
            'filename': test_filename,
            'path': test_filepath,
            'exists': os.path.exists(test_filepath),
            'size': os.path.getsize(test_filepath) if os.path.exists(test_filepath) else 0,
            'permissions': oct(os.stat(test_filepath).st_mode)[-3:] if os.path.exists(test_filepath) else None
        }
        
        # Step 5: Test creating a grid image
        logger.info("Test pipeline: capturing images from all cameras")
        images = camera_manager.capture_all_cameras()
        
        logger.info("Test pipeline: creating grid image")
        grid_img = camera_manager.create_grid_image(images)
        
        grid_filename = f'test_pipeline_grid_{int(time.time())}.jpg'
        grid_filepath = os.path.join(capture_dir, grid_filename)
        logger.info(f"Test pipeline: saving grid image to {grid_filepath}")
        
        grid_img.save(grid_filepath)
        
        grid_file_info = {
            'filename': grid_filename,
            'path': grid_filepath,
            'exists': os.path.exists(grid_filepath),
            'size': os.path.getsize(grid_filepath) if os.path.exists(grid_filepath) else 0,
            'permissions': oct(os.stat(grid_filepath).st_mode)[-3:] if os.path.exists(grid_filepath) else None
        }
        
        return jsonify({
            'success': True,
            'capture_directory': capture_dir_info,
            'test_file': file_info,
            'grid_file': grid_file_info
        })
        
    except Exception as e:
        logger.error(f"Error in test capture pipeline: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': str(traceback.format_exc())
        }), 500

@app.route('/debug')
def debug_index():
    """Render the debug page."""
    return render_template('debug_index.html', camera_count=4)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
