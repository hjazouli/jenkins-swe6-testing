import serial
import time

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 9600

class HardwareBridge:
    def __init__(self):
        print(f"Hardware Bridge: Connecting to Hardware on {SERIAL_PORT}...")
        self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        
        # Wait for the board to finish rebooting and send the boot signature
        timeout_start = time.time()
        print("   ↳ Waiting for board to boot...")
        while time.time() < timeout_start + 5.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if "--- BCM BOOTED ---" in line:
                print("   ↳ Board is ONLINE! ✅")
                break
        
        self.serial.timeout = 1.0
        self.serial.reset_input_buffer()

    def set_pedal(self, force: float):
        self.serial.write(f"P{force}\n".encode("utf-8"))

    def set_temp(self, temp: float):
        self.serial.write(f"T{temp}\n".encode("utf-8"))

    def set_speed(self, speed: float):
        self.serial.write(f"S{speed}\n".encode("utf-8"))

    def get_sw_version(self):
        """Queries the board for its software version."""
        self.serial.reset_input_buffer()
        self.serial.write(b"V\n")
        timeout_start = time.time()
        while time.time() < timeout_start + 2.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if "[VER]" in line:
                return line.replace("[VER]", "").strip()
        return "UNKNOWN"

    def get_status(self, wait_for_data=True):
        """Reads the board telemetry with raw output for debugging."""
        timeout_start = time.time()
        while time.time() < timeout_start + 4.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if not line: continue
            
            print(f"DEBUG-UART >> {line}")

            if "[ACK]" in line: continue

            # Recognize both [BCM] and [BCM-V101] (or any other versioned header)
            if "[BCM" in line:
                return line
        return ""

    def close(self):
        self.serial.close()
