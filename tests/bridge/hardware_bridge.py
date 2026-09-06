import serial
import serial.threaded
import time
import struct
import os
import logging
import queue
from datetime import datetime

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 115200

# --- Binary frame protocol -------------------------------------------------
# Wire format: START(0x7E) TYPE(1) LEN(1) PAYLOAD(LEN) CRC16_LO CRC16_HI
# Must match firmware/BCM_Firmware/Core/Src/main.c exactly (frame types,
# struct layout, and CRC algorithm).
FRAME_START = 0x7E

CMD_SET_PEDAL = 0x01
CMD_SET_SPEED = 0x02
CMD_SET_TEMP = 0x03
CMD_RESET = 0x04
CMD_SET_WEAR = 0x05

RESP_ACK = 0x10
RESP_NACK = 0x11
RESP_TELEMETRY = 0x20

# tick(u32), pedal/speed/wear/front/rear(f32 x5), status_flag(u8), chip_temp_c(i32)
TELEMETRY_STRUCT = "<IfffffBi"


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect).

    Bit-for-bit port of the firmware's crc16_ccitt() in main.c so both sides
    compute the identical checksum over TYPE+LEN+PAYLOAD.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_frame(frame_type: int, payload: bytes = b"") -> bytes:
    header = bytes([frame_type, len(payload)])
    crc = crc16_ccitt(header + payload)
    return bytes([FRAME_START]) + header + payload + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

# Console colors, keyed by the "tag" each Log method logs under.
_TAG_COLORS = {
    "INFO": "\033[36m",
    "TX": "\033[34m",
    "RX": "\033[35m",
    "TELEM": "\033[90m",
    "ERROR": "\033[31m",
}

# Human-readable description shown alongside each tag, e.g. "[TX : transmitting via UART]".
_TAG_DESCRIPTIONS = {
    "INFO": "Information",
    "TX": "Transmitting via UART",
    "RX": "Receiving via UART",
    "TELEM": "Telemetry sample",
    "ERROR": "Error",
    "VERBOSE": "Verbose output",
    "STAGE_START": "Stage start",
    "STAGE_END": "Stage end",
}


def _tag_and_caller(record, tag):
    """Builds the shared "[TAG : description] [module.py function : name]" prefix
    used by both the console and file formatters, so a reader can tell at a
    glance what kind of event this is and exactly which function logged it."""
    description = _TAG_DESCRIPTIONS.get(tag, tag.lower())
    return f"[{tag} : {description}] [{record.module}.py function : {record.funcName}]"


class _ConsoleFormatter(logging.Formatter):
    """Reproduces the bridge's original colored, tagged console output on top of stdlib logging."""

    def format(self, record):
        tag = getattr(record, "tag", record.levelname)
        message = record.getMessage()

        if tag == "TEST_START":
            return f"\n\033[1m\033[33m>>> {message}\033[0m"
        if tag == "TEST_END":
            return f"\033[1m\033[32m<<< {message}\033[0m\n"
        if tag == "STAGE_START":
            return f"\n\033[1m\033[34m>>> {message}\033[0m"
        if tag == "STAGE_END":
            color = "\033[1m\033[31m" if "FAILED" in message else "\033[1m\033[32m"
            return f"{color}<<< {message}\033[0m\n"

        ts = f"{self.formatTime(record, '%H:%M:%S')}.{int(record.msecs):03d}"
        color = _TAG_COLORS.get(tag, "")
        prefix = _tag_and_caller(record, tag)
        return f"{color}{ts} {prefix}\033[0m {message}"


class _FileFormatter(logging.Formatter):
    """Same "[TAG : description] [module.py function : name]" prefix as the
    console, minus ANSI colors, for session.log."""

    def format(self, record):
        tag = getattr(record, "tag", record.levelname)
        message = record.getMessage()
        ts = f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')},{int(record.msecs):03d}"
        prefix = _tag_and_caller(record, tag)
        return f"{ts} {prefix} {message}"


_logger = logging.getLogger("hardware_bridge")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_ConsoleFormatter())
_console_handler.setLevel(logging.INFO)  # keep per-sample TELEM debug lines out of the terminal
_logger.addHandler(_console_handler)


class Log:
    """Thin, tag-based facade over the stdlib `logging` module.

    Keeps the same call sites (Log.info/trace_tx/.../test_end) used throughout
    the test suite, while getting level filtering, thread-safe handlers, and
    optional file output for free from `logging`.
    """

    @staticmethod
    def attach_file_handler(session_dir, filename="session.log"):
        """Mirror console output (minus ANSI colors) into <session_dir>/<filename>."""
        if any(isinstance(h, logging.FileHandler) for h in _logger.handlers):
            return
        handler = logging.FileHandler(os.path.join(session_dir, filename))
        handler.setFormatter(_FileFormatter())
        _logger.addHandler(handler)

    # stacklevel=2 on every call below: without it, the logging module would
    # report the caller as this Log method itself (e.g. "trace_tx") since
    # that's the immediate caller of _logger.*(). Skipping one frame up
    # attributes %(module)s/%(funcName)s to whoever actually called Log.*().

    @staticmethod
    def info(msg):
        _logger.info(msg, extra={"tag": "INFO"}, stacklevel=2)

    @staticmethod
    def trace_tx(msg):
        _logger.info(msg, extra={"tag": "TX"}, stacklevel=2)

    @staticmethod
    def trace_rx(msg):
        _logger.info(msg, extra={"tag": "RX"}, stacklevel=2)

    @staticmethod
    def debug(msg):
        # Telemetry spam: drops out automatically if the logger level is raised above DEBUG.
        _logger.debug(msg, extra={"tag": "TELEM"}, stacklevel=2)

    @staticmethod
    def verbose(msg):
        # High-volume detail (e.g. raw compiler/flasher output): always written
        # to the log file, filtered out of the console (same as TELEM).
        _logger.debug(msg, extra={"tag": "VERBOSE"}, stacklevel=2)

    @staticmethod
    def test_start(name, description=""):
        suffix = f" ({description})" if description else ""
        _logger.info(f"START TEST: {name}{suffix}", extra={"tag": "TEST_START"}, stacklevel=2)

    @staticmethod
    def test_end(name):
        _logger.info(f"END TEST:   {name}", extra={"tag": "TEST_END"}, stacklevel=2)

    @staticmethod
    def stage_start(name):
        _logger.info(f"STAGE: {name}", extra={"tag": "STAGE_START"}, stacklevel=2)

    @staticmethod
    def stage_end(name, ok=True):
        status = "OK" if ok else "FAILED"
        _logger.info(f"STAGE: {name} [{status}]", extra={"tag": "STAGE_END"}, stacklevel=2)

    @staticmethod
    def error(msg):
        _logger.error(msg, extra={"tag": "ERROR"}, stacklevel=2)


class BcmFrameReader(serial.threaded.Protocol):
    """Parses the BCM's binary CRC16-framed protocol.

    Deliberately independent of any serial port or file I/O: it only reacts
    to `data_received()`, so the protocol logic can be unit tested by
    feeding it raw frame bytes directly, without a board or an open port,
    e.g.:

        reader = BcmFrameReader()
        reader.data_received(build_frame(RESP_ACK))
        assert reader.response_queue.get_nowait() == RESP_ACK

    A length-prefixed binary frame (rather than a text line) is required
    here: a telemetry payload's raw float bytes can legally contain 0x0D/0x0A,
    which would falsely look like a line terminator to a text-based reader.
    """

    # Frame parser states
    _WAIT_START, _WAIT_TYPE, _WAIT_LEN, _WAIT_PAYLOAD, _WAIT_CRC1, _WAIT_CRC2 = range(6)

    def __init__(self):
        self.transport = None
        self.response_queue = queue.Queue()
        self.latest_telemetry = {}
        self.on_telemetry = None  # optional callback(dict), set by the owner
        self._reset_parser()

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.transport = None
        if exc:
            Log.error(f"Serial connection lost: {exc}")

    def _reset_parser(self):
        self._state = self._WAIT_START
        self._frame_type = 0
        self._frame_len = 0
        self._payload = bytearray()
        self._crc_lo = 0

    def data_received(self, data: bytes):
        for byte in data:
            self._feed_byte(byte)

    def _feed_byte(self, byte):
        if self._state == self._WAIT_START:
            if byte == FRAME_START:
                self._state = self._WAIT_TYPE
        elif self._state == self._WAIT_TYPE:
            self._frame_type = byte
            self._state = self._WAIT_LEN
        elif self._state == self._WAIT_LEN:
            self._frame_len = byte
            self._payload = bytearray()
            self._state = self._WAIT_PAYLOAD if self._frame_len > 0 else self._WAIT_CRC1
        elif self._state == self._WAIT_PAYLOAD:
            self._payload.append(byte)
            if len(self._payload) >= self._frame_len:
                self._state = self._WAIT_CRC1
        elif self._state == self._WAIT_CRC1:
            self._crc_lo = byte
            self._state = self._WAIT_CRC2
        elif self._state == self._WAIT_CRC2:
            recv_crc = self._crc_lo | (byte << 8)
            self._handle_frame(self._frame_type, bytes(self._payload), recv_crc)
            self._reset_parser()

    def _handle_frame(self, frame_type, payload, recv_crc):
        calc_crc = crc16_ccitt(bytes([frame_type, len(payload)]) + payload)
        if calc_crc != recv_crc:
            Log.error(f"CRC mismatch on frame type 0x{frame_type:02X} (dropped)")
            return

        if frame_type in (RESP_ACK, RESP_NACK):
            self.response_queue.put(frame_type)
        elif frame_type == RESP_TELEMETRY:
            expected_size = struct.calcsize(TELEMETRY_STRUCT)
            if len(payload) != expected_size:
                Log.error(f"Telemetry frame size mismatch: got {len(payload)}, expected {expected_size}")
                return
            tick, pedal, speed, wear, front, rear, flag, chip_c = struct.unpack(TELEMETRY_STRUCT, payload)
            d = {
                "t": tick, "p": pedal, "s": speed, "w": wear,
                "f": front, "r": rear, "flag": flag, "chip_c": chip_c,
                "lights": "ACTIVE" if (flag & 0x01) else "OFF",
            }
            self.latest_telemetry = d
            if self.on_telemetry:
                self.on_telemetry(d)

    def write_frame(self, frame_type: int, payload: bytes = b""):
        self.transport.write(build_frame(frame_type, payload))


class HardwareBridge:
    _session_dir = None

    def __init__(self):
        if HardwareBridge._session_dir is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            HardwareBridge._session_dir = os.path.join("test_results", f"session_{timestamp}")
            os.makedirs(HardwareBridge._session_dir, exist_ok=True)
            Log.attach_file_handler(HardwareBridge._session_dir)

        Log.info(f"Opening Hardware Link on {SERIAL_PORT}...")

        try:
            self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        except Exception as e:
            Log.error(f"Failed to open port: {e}")
            raise

        # Initialize Telemetry CSV
        time_suffix = datetime.now().strftime('%H%M%S_%f')[:-3]
        self.csv_filename = os.path.join(HardwareBridge._session_dir, f"telemetry_{time_suffix}.csv")
        self.csv_file = open(self.csv_filename, "w")
        self.csv_file.write("Mac_Time,ECU_Tick,Pedal_pct,Speed_kmh,Wear_pct,Front_bar,Rear_bar,Lights,Flags,Chip_Temp_C\n")
        self.csv_file.flush()
        Log.info(f"Telemetry logging started: {self.csv_filename}")

        # Start the background reader thread (serial.threaded owns the thread
        # lifecycle and byte-buffering; BcmFrameReader just reacts to frames)
        self._reader_thread = serial.threaded.ReaderThread(self.serial, BcmFrameReader)
        self._reader_thread.start()
        _, self.protocol = self._reader_thread.connect()
        self.protocol.on_telemetry = self._record_telemetry

        # Wait for board interaction
        timeout_start = time.time()
        while time.time() < timeout_start + 3.0:
            if self.protocol.latest_telemetry:
                Log.info("Hardware synchronization successful.")
                break
            time.sleep(0.1)

        self.serial.reset_input_buffer()

    def _record_telemetry(self, d):
        """Callback invoked by BcmFrameReader for every parsed telemetry frame.

        Writes each sample to both the CSV (for plotting, see
        scripts/visualize_telemetry.py) and, as a plain-text line, to the
        session's session.log (via Log.debug) so a human-readable trace is
        available alongside the structured data.
        """
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        l_val = d.get('lights', d.get('l', "OFF"))
        l_int = 1 if l_val == "ACTIVE" else 0
        csv_line = f"{ts},{d.get('t', 0)},{d.get('p', 0)},{d.get('s', 0)},{d.get('w', 0)},{d.get('f', 0)},{d.get('r', 0)},{l_int},{d.get('flag', 0)},{d.get('chip_c', 0)}\n"
        self.csv_file.write(csv_line)
        self.csv_file.flush()

        flag = int(d.get('flag', 0))
        Log.debug(
            f"tick={d.get('t', 0)} pedal={d.get('p', 0)} speed={d.get('s', 0)} "
            f"wear={d.get('w', 0)} front={d.get('f', 0)} rear={d.get('r', 0)} "
            f"lights={l_val} flag=0x{flag:02X} chip_c={d.get('chip_c', 0)}"
        )

    def _send_command(self, frame_type: int, value: float = None):
        """Sends a framed command and waits for ACK/NACK from the background reader."""
        payload = struct.pack("<f", value) if value is not None else b""
        Log.trace_tx(f"type=0x{frame_type:02X} payload={payload.hex()}")

        # Clear queue of any stale ACKs
        while not self.protocol.response_queue.empty():
            self.protocol.response_queue.get()

        self.protocol.write_frame(frame_type, payload)

        # Wait for the reader to signal ACK/NACK reception
        try:
            response = self.protocol.response_queue.get(timeout=1.5)
            if response == RESP_ACK:
                Log.trace_rx("ACK")
            else:
                Log.error(f"NACK received for command 0x{frame_type:02X} (bad CRC?)")
        except queue.Empty:
            Log.error(f"Command 0x{frame_type:02X} timeout (No ACK)")

    def set_pedal(self, force: float):
        self._send_command(CMD_SET_PEDAL, force)

    def set_speed(self, speed: float):
        self._send_command(CMD_SET_SPEED, speed)

    def set_temp(self, temp: float):
        self._send_command(CMD_SET_TEMP, temp)

    def set_wear(self, wear: float):
        self._send_command(CMD_SET_WEAR, wear)

    def reset(self):
        self._send_command(CMD_RESET)

    def get_status(self):
        """Returns the most recent telemetry captured by the background reader."""
        return self.protocol.latest_telemetry

    def close(self):
        if hasattr(self, "_reader_thread"):
            Log.info("Closing hardware link.")
            self._reader_thread.close()  # stops the thread and closes the port

        if hasattr(self, "csv_file") and self.csv_file:
            Log.info("Stopping telemetry logging.")
            self.csv_file.close()
