import serial
import serial.tools.list_ports
import time
import sys

def find_nucleo_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "usbmodem" in port.device.lower() or "stlink" in port.description.lower():
            return port.device
    return None

def main():
    print("--- BCM SERIAL MONITOR ---")
    
    port = find_nucleo_port()
    if not port:
        print("Error: Nucleo board not found. Is it plugged in?")
        sys.exit(1)
        
    print(f"Connecting to {port} at 9600 baud...")
    
    try:
        # We use 9600 because our current firmware is set to 9600
        ser = serial.Serial(port, 9600, timeout=1)
        print("Connected! Listening for BCM Telemetry (Ctrl+C to stop)...\n")
        
        while True:
            if ser.in_waiting > 0:
                # Read raw bytes to avoid decoding errors
                line = ser.read(ser.in_waiting).decode('ascii', errors='replace')
                print(line, end='', flush=True)
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if 'ser' in locals():
            ser.close()

if __name__ == "__main__":
    main()
