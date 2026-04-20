import serial
import time

PORT = "/dev/tty.usbmodem103"
BAUD = 9600

print(f"--- BCM SMOKE TEST ---")
try:
    s = serial.Serial(PORT, BAUD, timeout=1)
    print(f"Connected to {PORT}")
    
    # 1. Hardware Reset (Toggle DTR to reboot Nucleo)
    print("Resetting board...")
    s.dtr = False
    time.sleep(0.1)
    s.dtr = True
    time.sleep(2)
    
    # 2. listen for boot message
    print("Listening for 3 seconds...")
    start = time.time()
    while time.time() < start + 3:
        line = s.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"BOARD >> {line}")

    # 3. Send command
    print("\nSending 'P100.0'...")
    s.write(b"P100.0\n")
    
    # 4. Listen for ACK or Telemetry
    print("Waiting for echo and response...")
    start = time.time()
    while time.time() < start + 5.0:
        # We read byte by byte to see the echo clearly
        char = s.read(1).decode('utf-8', errors='ignore')
        if char:
            print(f"{char}", end="", flush=True)
            if char == "\n": print("   ↳ (End of Line)")
            
    s.close()
    print("\nSmoke test finished.")

except Exception as e:
    print(f"ERROR: {e}")
