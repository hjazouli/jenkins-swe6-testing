import serial
import time

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 115200

class Color:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

class HardwareBridge:
    def __init__(self):
        print(f"{Color.BOLD}Hardware Bridge: Connecting to Hardware on {SERIAL_PORT}...{Color.END}")
        self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)

        # Wait for board boot
        timeout_start = time.time()
        print(f" {Color.BLUE}↳ Waiting for board to boot...{Color.END}")
        while time.time() < timeout_start + 5.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if "--- BCM BOOTED ---" in line:
                print(f" {Color.GREEN}↳ Board is ONLINE! ✅{Color.END}")
                break

        self.serial.timeout = 1.0
        self.serial.reset_input_buffer()

    def _send_command(self, cmd: str):
        """Sends a command and waits for an [ACK] to verify reception."""
        print(f" {Color.BLUE}📤 SENDING: {cmd.strip()}{Color.END}")
        self.serial.write(cmd.encode("utf-8"))
        
        # Pacing: Give the command time to be processed
        time.sleep(0.1) 
        
        # Verify reception via ACK
        timeout_start = time.time()
        while time.time() < timeout_start + 1.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if line:
                print(f" {Color.YELLOW}DEBUG-UART >> {line}{Color.END}")
            if "[ACK]" in line:
                print(f" {Color.GREEN}✅ COMMAND ACKNOWLEDGED{Color.END}")
                return
        
        print(f" {Color.RED}⚠️ WARNING: NO ACK FOR {cmd.strip()}{Color.END}")

    def set_pedal(self, force: float):
        self._send_command(f"P{force}\n")

    def set_temp(self, temp: float):
        self._send_command(f"T{temp}\n")

    def set_speed(self, speed: float):
        self._send_command(f"S{speed}\n")

    def reset(self):
        """Forces a global ECU state reset."""
        self._send_command("R\n")

    def get_sw_version(self):
        """Queries the board for its software version."""
        self.serial.reset_input_buffer()
        self.serial.write(b"V\n")
        timeout_start = time.time()
        while time.time() < timeout_start + 2.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if "[VER]" in line:
                version = line.replace("[VER]", "").strip()
                print(f" {Color.GREEN}🏷️ Found Version: {version}{Color.END}")
                return version
        return "UNKNOWN"

    def get_status(self, wait_for_data=True):
        """Reads the board telemetry with raw output for debugging."""
        timeout_start = time.time()
        while time.time() < timeout_start + 4.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            print(f" {Color.YELLOW}DEBUG-UART >> {line}{Color.END}")

            if "[ACK]" in line:
                continue

            # Recognize both [BCM] and [BCM-V101]
            if "[BCM" in line:
                return line
        return ""

    def close(self):
        self.serial.close()
