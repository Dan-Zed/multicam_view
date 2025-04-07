"""
Tests for the Flask application routes
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock
from PIL import Image

import cam

class TestFlaskApp:
    """Test suite for Flask application routes."""
    
    def test_index_route(self, app):
        """Test the index route."""
        response = app.get('/')
        assert response.status_code == 200
        assert b'multicam view' in response.data
    
    def test_camera_info_route(self, app, mock_camera_manager):
        """Test the camera_info route."""
        # Set up mock properties
        mock_camera_manager.camera_count = 4
        mock_camera_manager.current_camera = 1
        mock_camera_manager.is_cycling = True
        mock_camera_manager.cycle_interval = 2.0
        
        # Set the app's camera_manager to our mock
        old_cm = cam.camera_manager
        cam.camera_manager = mock_camera_manager
        
        try:
            response = app.get('/camera_info')
            data = json.loads(response.data)
            
            assert response.status_code == 200
            assert data['success'] is True
            assert data['camera_count'] == 4
            assert data['current_camera'] == 1
            assert data['cycling'] is True
            assert data['cycle_interval'] == 2.0
        finally:
            # Restore the original camera_manager
            cam.camera_manager = old_cm
    
    def test_select_camera_route(self, app, mock_camera_manager):
        """Test the select_camera route."""
        # Set up mock behavior
        mock_camera_manager.select_camera.return_value = True
        mock_camera_manager.is_cycling = True
        
        # Set the app's camera_manager to our mock
        old_cm = cam.camera_manager
        cam.camera_manager = mock_camera_manager
        
        try:
            response = app.get('/select_camera/2')
            data = json.loads(response.data)
            
            assert response.status_code == 200
            assert data['success'] is True
            assert data['camera'] == 2
            
            # Should have called select_camera with camera_id 2
            mock_camera_manager.select_camera.assert_called_with(2)
            
            # Should have stopped cycling
            mock_camera_manager.stop_camera_cycle.assert_called_once()
        finally:
            # Restore the original camera_manager
            cam.camera_manager = old_cm
    
    def test_toggle_cycle_route(self, app, mock_camera_manager):
        """Test the toggle_cycle route."""
        # Test stopping cycling
        mock_camera_manager.is_cycling = True
        
        # Set the app's camera_manager to our mock
        old_cm = cam.camera_manager
        cam.camera_manager = mock_camera_manager
        
        try:
            response = app.get('/toggle_cycle')
            data = json.loads(response.data)
            
            assert response.status_code == 200
            assert data['success'] is True
            assert data['status'] == 'stopped'
            
            # Should have called stop_camera_cycle
            mock_camera_manager.stop_camera_cycle.assert_called_once()
            
            # Test starting cycling
            mock_camera_manager.reset_mock()
            mock_camera_manager.is_cycling = False
            
            response = app.get('/toggle_cycle')
            data = json.loads(response.data)
            
            assert response.status_code == 200
            assert data['success'] is True
            assert data['status'] == 'started'
            
            # Should have called start_camera_cycle
            mock_camera_manager.start_camera_cycle.assert_called_once()
        finally:
            # Restore the original camera_manager
            cam.camera_manager = old_cm
    
    def test_capture_route(self, app, mock_camera_manager, test_images):
        """Test the capture route."""
        # Set up mock behavior
        mock_camera_manager.capture_all_cameras.return_value = test_images
        
        # Create mock grid image
        grid_img = Image.new('RGB', (1280, 960), color=(200, 200, 200))
        mock_camera_manager.create_grid_image.return_value = grid_img
        
        # Set the app's camera_manager to our mock
        old_cm = cam.camera_manager
        cam.camera_manager = mock_camera_manager
        
        try:
            response = app.get('/capture')
            data = json.loads(response.data)
            
            assert response.status_code == 200
            assert data['success'] is True
            assert 'filenames' in data
            assert 'grid_filename' in data
            assert len(data['filenames']) == 4
            
            # Check that capture_all_cameras was called
            mock_camera_manager.capture_all_cameras.assert_called_once()
            
            # Check that create_grid_image was called with our test images
            mock_camera_manager.create_grid_image.assert_called_once()
            
            # Check that the images were saved to the captures directory
            captures_dir = app.application.config['CAPTURE_FOLDER']
            
            # Should have saved 5 files (4 individual + 1 grid)
            saved_files = os.listdir(captures_dir)
            assert len(saved_files) == 5
            
            # At least one file should be a grid file
            grid_files = [f for f in saved_files if '_grid.jpg' in f]
            assert len(grid_files) == 1
        finally:
            # Restore the original camera_manager
            cam.camera_manager = old_cm
    
    def test_latest_capture_route(self, app):
        """Test the latest_capture route."""
        # Create a test grid image in the captures directory
        captures_dir = app.application.config['CAPTURE_FOLDER']
        test_grid_file = os.path.join(captures_dir, 'capture_1_grid.jpg')
        
        # Create a simple test image
        test_img = Image.new('RGB', (100, 100), color=(150, 150, 150))
        test_img.save(test_grid_file)
        
        # Test the route
        response = app.get('/latest_capture')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert data['filename'] == 'capture_1_grid.jpg'
        
        # Test with no captures
        os.remove(test_grid_file)
        response = app.get('/latest_capture')
        
        assert response.status_code == 404
    
    def test_serve_capture_route(self, app):
        """Test the serve_capture route."""
        # Create a test image in the captures directory
        captures_dir = app.application.config['CAPTURE_FOLDER']
        test_file = os.path.join(captures_dir, 'test_image.jpg')
        
        # Create a simple test image
        test_img = Image.new('RGB', (100, 100), color=(150, 150, 150))
        test_img.save(test_file)
        
        # Test the route
        response = app.get('/captures/test_image.jpg')
        
        assert response.status_code == 200
        assert response.mimetype == 'image/jpeg'
        
        # Test with non-existent file
        response = app.get('/captures/nonexistent.jpg')
        assert response.status_code == 404
    
    def test_debug_captures_route(self, app):
        """Test the debug_captures route."""
        # Create a test file in the captures directory
        captures_dir = app.application.config['CAPTURE_FOLDER']
        test_file = os.path.join(captures_dir, 'test_debug.jpg')
        
        # Create a simple test image
        test_img = Image.new('RGB', (100, 100), color=(150, 150, 150))
        test_img.save(test_file)
        
        # Test the route
        response = app.get('/debug/captures')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert data['directory'] == captures_dir
        assert data['file_count'] == 1
        assert len(data['files']) == 1
        assert data['files'][0]['name'] == 'test_debug.jpg'
    
    def test_debug_test_capture_route(self, app, mock_camera_manager):
        """Test the debug_test_capture route."""
        # Set up mock behavior
        test_img = Image.new('RGB', (640, 480), color=(100, 100, 100))
        mock_camera_manager.capture_image.return_value = test_img
        
        # Set the app's camera_manager to our mock
        old_cm = cam.camera_manager
        cam.camera_manager = mock_camera_manager
        
        try:
            response = app.get('/debug/test_capture')
            data = json.loads(response.data)
            
            assert response.status_code == 200
            assert data['success'] is True
            assert 'file' in data
            
            # Should have called capture_image with camera 0
            mock_camera_manager.capture_image.assert_called_with(0)
            
            # Should have saved the file
            captures_dir = app.application.config['CAPTURE_FOLDER']
            saved_files = os.listdir(captures_dir)
            assert len(saved_files) == 1
            
            # File should match the one in the response
            assert saved_files[0] == data['file']['filename']
        finally:
            # Restore the original camera_manager
            cam.camera_manager = old_cm
