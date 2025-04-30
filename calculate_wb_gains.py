#!/usr/bin/env python3
"""
White Balance Calibration Script

This script calculates white balance gains using the grey-world assumption from a captured image.
It can be used to determine appropriate red and blue gains for camera configuration.

Usage:
    python calculate_wb_gains.py path/to/image.jpg

Output:
    Prints the calculated red and blue gains based on the grey-world assumption.
"""

import sys
import os
import numpy as np
from PIL import Image
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wb_calibration')

def calculate_wb_gains(image_path):
    """
    Calculate white balance gains using the grey-world assumption.
    
    Parameters:
    -----------
    image_path : str
        Path to the input image
    
    Returns:
    --------
    tuple
        (red_gain, blue_gain)
    """
    try:
        # Load the image
        logger.info(f"Loading image: {image_path}")
        img = Image.open(image_path)
        
        # Convert to NumPy array
        image_array = np.array(img)
        logger.info(f"Image loaded with shape: {image_array.shape}")
        
        # Check if it's an RGB image
        if len(image_array.shape) != 3 or image_array.shape[2] != 3:
            if len(image_array.shape) == 3 and image_array.shape[2] == 4:
                # RGBA image, drop alpha channel
                logger.info("RGBA image detected, dropping alpha channel")
                image_array = image_array[:, :, :3]
            else:
                logger.error(f"Expected RGB image, got shape: {image_array.shape}")
                return None, None
        
        # Calculate average values for each channel
        avg_r = np.mean(image_array[:, :, 0])
        avg_g = np.mean(image_array[:, :, 1])
        avg_b = np.mean(image_array[:, :, 2])
        
        logger.info(f"Average R: {avg_r:.2f}, G: {avg_g:.2f}, B: {avg_b:.2f}")
        
        # Calculate gains based on grey-world assumption
        # The assumption is that the average of all channels should be equal
        red_gain = avg_g / avg_r if avg_r > 0 else 1.0
        blue_gain = avg_g / avg_b if avg_b > 0 else 1.0
        
        logger.info(f"Calculated red_gain: {red_gain:.4f}, blue_gain: {blue_gain:.4f}")
        
        return red_gain, blue_gain
        
    except Exception as e:
        logger.error(f"Error calculating white balance gains: {e}", exc_info=True)
        return None, None

def analyze_image_channels(image_path):
    """
    Analyze the color channels of an image in detail.
    
    Parameters:
    -----------
    image_path : str
        Path to the input image
    
    Returns:
    --------
    dict
        Dictionary with channel statistics
    """
    try:
        # Load the image
        img = Image.open(image_path)
        image_array = np.array(img)
        
        # Drop alpha channel if present
        if len(image_array.shape) == 3 and image_array.shape[2] == 4:
            image_array = image_array[:, :, :3]
        
        # Extract channels
        r_channel = image_array[:, :, 0]
        g_channel = image_array[:, :, 1]
        b_channel = image_array[:, :, 2]
        
        # Calculate statistics for each channel
        stats = {
            'red': {
                'mean': np.mean(r_channel),
                'median': np.median(r_channel),
                'min': np.min(r_channel),
                'max': np.max(r_channel),
                'std': np.std(r_channel)
            },
            'green': {
                'mean': np.mean(g_channel),
                'median': np.median(g_channel),
                'min': np.min(g_channel),
                'max': np.max(g_channel),
                'std': np.std(g_channel)
            },
            'blue': {
                'mean': np.mean(b_channel),
                'median': np.median(b_channel),
                'min': np.min(b_channel),
                'max': np.max(b_channel),
                'std': np.std(b_channel)
            }
        }
        
        # Calculate overall brightness
        luminance = 0.299 * r_channel + 0.587 * g_channel + 0.114 * b_channel
        stats['luminance'] = {
            'mean': np.mean(luminance),
            'median': np.median(luminance),
            'min': np.min(luminance),
            'max': np.max(luminance),
            'std': np.std(luminance)
        }
        
        # Calculate ratios between channels
        stats['ratios'] = {
            'r_to_g': np.mean(r_channel) / np.mean(g_channel) if np.mean(g_channel) > 0 else 0,
            'b_to_g': np.mean(b_channel) / np.mean(g_channel) if np.mean(g_channel) > 0 else 0,
            'r_to_b': np.mean(r_channel) / np.mean(b_channel) if np.mean(b_channel) > 0 else 0
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error analyzing image channels: {e}", exc_info=True)
        return None

def main():
    parser = argparse.ArgumentParser(description="Calculate white balance gains from an image using grey-world assumption.")
    parser.add_argument("image_path", help="Path to the input image")
    parser.add_argument("--detailed", action="store_true", help="Show detailed channel analysis")
    args = parser.parse_args()
    
    # Validate file exists
    if not os.path.isfile(args.image_path):
        logger.error(f"Input file does not exist: {args.image_path}")
        sys.exit(1)
    
    # Calculate white balance gains
    red_gain, blue_gain = calculate_wb_gains(args.image_path)
    
    if red_gain is None or blue_gain is None:
        logger.error("Failed to calculate white balance gains")
        sys.exit(1)
    
    # Print results
    print("\n===== White Balance Gains (Grey-World Assumption) =====")
    print(f"Image: {args.image_path}")
    print(f"Red Gain:  {red_gain:.4f}")
    print(f"Blue Gain: {blue_gain:.4f}")
    print("")
    print("To set these in camera configuration:")
    print(f"ColourGains: ({red_gain:.4f}, {blue_gain:.4f})")
    print("================================================")
    
    # Show detailed analysis if requested
    if args.detailed:
        stats = analyze_image_channels(args.image_path)
        if stats:
            print("\n===== Detailed Channel Analysis =====")
            for channel, channel_stats in stats.items():
                if channel != 'ratios':
                    print(f"\n{channel.upper()}:")
                    for stat_name, value in channel_stats.items():
                        print(f"  {stat_name}: {value:.2f}")
            
            print("\nCHANNEL RATIOS:")
            for ratio_name, value in stats['ratios'].items():
                print(f"  {ratio_name}: {value:.4f}")
            print("====================================")

if __name__ == "__main__":
    main()
