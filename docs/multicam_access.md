**Camera Module**: Arducam camarray HAT with IMX519 sensors

### Key Configuration
 **Camera Multiplexer Control** (at I2C address 0x24 on bus 11):
    
    ```bash
    # Select single channel 0
    i2cset -y 11 0x24 0x24 0x02
    
    # Select single channel 1
    i2cset -y 11 0x24 0x24 0x12
    
    # Select single channel 2
    i2cset -y 11 0x24 0x24 0x22
    
    # Select single channel 3
    i2cset -y 11 0x24 0x24 0x32
    
    # Set to four-in-one mode (default)
    i2cset -y 11 0x24 0x24 0x00
    ```
    
### Important Notes
- The multiplexer communicates over I2C bus 11 (not bus 10 as some documentation suggests)
- When switching cameras, allow a brief delay for the multiplexer to switch
- Each camera remains at its fixed I2C address (typically 0x1a for IMX519)
- The multiplexer selects which camera is active through the control commands