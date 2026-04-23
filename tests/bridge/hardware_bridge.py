import serial
import time
import re
import threading
from datetime import datetime
from typing import Dict, Optional


SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 115200


class Log:
    @staticmethod
    def _timestamp():
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    @staticmethod
    def info(msg):
        print(f"{Log._timestamp()}[INFO]  HIL_BRIDGE: {msg}")

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

        self.serial.timeout = 0.1
        self.serial.reset_input_buffer()

        # Threading & Synchronization
        self._latest_status: Dict = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ack_event = threading.Event()
        
        # Initialize Trace Recorder
        self.trace_filename = f"hil_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.trace_file = open(self.trace_filename, "w")
        self.trace_file.write(f"# HIL ASYNC TRACE START: {datetime.now().isoformat()}\n")
        self.trace_file.write("# MAC_TIME | UART_RAW\n")
        
        # Start Background Reader
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        Log.info(f"Background Recorder started: {self.trace_filename}")

    def _log_to_trace(self, raw_line: str):
        """Internal helper to write to the persistent trace file."""
        if hasattr(self, "trace_file") and self.trace_file:
            ts = Log._timestamp()
            self.trace_file.write(f"{ts} | {raw_line}\n")
            self.trace_file.flush() # Ensure data is saved even if crash happens

    def _read_loop(self):
        """Continuous background loop for gapless data capture."""
        while not self._stop_event.is_set():
            try:
                line = self.serial.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                
                self._log_to_trace(f"RX: {line}")

                if "[ACK]" in line or "[SYS] RESET" in line:
                    self._ack_event.set()
                
                if "[BCM" in line:
                    self._parse_telemetry(line)
            except Exception as e:
                if not self._stop_event.is_set():
                    Log.error(f"Reader Thread Error: {e}")

    def _parse_telemetry(self, line: str):
        """Update shared state with latest BCM data."""
        # [BCM-V101] T:1234 P:50 S:60 F:40 R:35 L:OFF FLAG:0
        parts = re.findall(r"(\w+):([\w.]+)", line)
        data = {k.lower(): v for k, v in parts}
        if "t" in data:
            with self._lock:
                # Type conversion
                self._latest_status = {
                    "tick": int(data.get("t", 0)),
                    "pedal": int(data.get("p", 0)),
                    "speed": int(data.get("s", 0)),
                    "wear": int(data.get("w", 0)),
                    "front": int(data.get("f", 0)),
                    "rear": int(data.get("r", 0)),
                    "lights": data.get("lights", data.get("l", "OFF")),
                    "flag": int(data.get("flag", "0"), 16) if "0x" in data.get("flag", "") else int(data.get("flag", "0"))
                }
                
                # Log debug for user awareness
                p, s, w = self._latest_status['pedal'], self._latest_status['speed'], self._latest_status['wear']
                f, r, l = self._latest_status['front'], self._latest_status['rear'], self._latest_status['lights']
                fl = self._latest_status['flag']
                Log.debug(f"P={p}% S={s}km/h W={w}% F={f} R={r} L={l} FLAG={fl}")

    def _send_command(self, cmd: str):
        """Sends a command and waits for the background thread to signal an ACK."""
        self._ack_event.clear()
        clean_cmd = cmd.strip()
        Log.trace_tx(clean_cmd)
        self._log_to_trace(f"TX: {clean_cmd}")
        self.serial.write(cmd.encode("utf-8"))

        # Wait for the background thread to flag an ACK
        if not self._ack_event.wait(timeout=1.5):
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

    def get_status(self) -> Dict:
        """Retrieves the latest telemetry, waiting for initial capture if needed."""
        timeout_start = time.time()
        while time.time() < timeout_start + 2.0:
            with self._lock:
                if self._latest_status:
                    return self._latest_status.copy()
            time.sleep(0.05)
        return {}

    def close(self):
        self._stop_event.set()
        
        if hasattr(self, "trace_file") and self.trace_file:
            Log.info("Stopping Trace Recorder.")
            self.trace_file.write(f"# HIL ASYNC TRACE END: {datetime.now().isoformat()}\n")
            self.trace_file.close()

        if hasattr(self, "serial"):
            Log.info("Closing hardware link.")
            self.serial.close()
