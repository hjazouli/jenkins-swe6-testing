import serial
import time
import re
from datetime import datetime

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 115200


class Log:
    @staticmethod
    def _timestamp():
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    @staticmethod
    def info(msg):
        print(f"{Log._timestamp()} [INFO]  HIL_BRIDGE: {msg}")

    @staticmethod
    def trace_tx(msg):
        print(f"{Log._timestamp()} [TRACE] UART_TX: {msg}")

    @staticmethod
    def trace_rx(msg):
        print(f"{Log._timestamp()} [TRACE] UART_RX: {msg}")

    @staticmethod
    def debug(msg):
        # Slightly dimmer for telemetry spam
        print(f"\033[2m{Log._timestamp()} [DEBUG] BCM_TELEM: {msg}\033[0m")

    @staticmethod
    def test_start(name, description=""):
        print(f"\n{Log._timestamp()} [INFO]  >>> START_TEST: {name} ({description})")

    @staticmethod
    def test_end(name):
        print(f"{Log._timestamp()} [INFO]  <<< END_TEST: {name}")

    @staticmethod
    def error(msg):
        print(f"\033[31m{Log._timestamp()} [ERROR] HIL_BRIDGE: {msg}\033[0m")


class HardwareBridge:
    def __init__(self):
        # We now use the standard Log.info instead of custom connect boxes
        Log.info(f"Opening Hardware Link on {SERIAL_PORT}...")

        try:
            self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        except Exception as e:
            Log.error(f"Failed to open port: {e}")
            raise

        # Wait for board interaction
        timeout_start = time.time()
        while time.time() < timeout_start + 2.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if "BCM" in line or "BOOTING" in line:
                Log.info("Hardware synchronization successful.")
                break

        self.serial.timeout = 0.5
        self.serial.reset_input_buffer()

    def _send_command(self, cmd: str):
        """Sends a command with industry-standard TRACE logging."""
        clean_cmd = cmd.strip()
        Log.trace_tx(clean_cmd)
        self.serial.write(cmd.encode("utf-8"))

        # Verify reception via ACK
        timeout_start = time.time()
        while time.time() < timeout_start + 1.2:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if line:
                Log.trace_rx(line)
            if "[ACK]" in line or "[SYS] RESET" in line:
                return

        Log.error(f"Command '{clean_cmd}' timeout (no ACK)")

    def set_pedal(self, force: float):
        self._send_command(f"P{force}\n")

    def set_speed(self, speed: float):
        self._send_command(f"S{speed}\n")

    def set_temp(self, temp: float):
        self._send_command(f"T{temp}\n")

    def set_wear(self, wear: float):
        self._send_command(f"W{wear}\n")

    def reset(self):
        self._send_command("R\n")

    def get_status(self):
        """Captures hardware telemetry and renders it as a structured log entry."""
        timeout_start = time.time()
        while time.time() < timeout_start + 3.0:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if not line or "[BCM" not in line:
                continue

            # Parse key-value pairs
            parts = re.findall(r"(\w+):([\w.]+)", line)
            data = {k: v for k, v in parts}

            p = data.get("P", "0")
            s = data.get("S", "0")
            w = data.get("W", "0")
            f = data.get("F", "0")
            r = data.get("R", "0")
            l = data.get("Lights", "OFF")
            fl = data.get("FLAG", "0")

            Log.debug(f"P={p}% S={s}km/h W={w}% F={f} R={r} L={l} FLAG={fl}")
            return line

        return ""

    def close(self):
        if hasattr(self, "serial"):
            Log.info("Closing hardware link.")
            self.serial.close()
