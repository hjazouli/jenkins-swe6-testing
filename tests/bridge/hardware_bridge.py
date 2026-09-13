import serial
import serial.threaded
import time
import struct
import os
import logging
import queue
from datetime import datetime

SERIAL_PORT = "/dev/tty.usbmodem1103"
BAUD_RATE = 115200

# tests/bridge/hardware_bridge.py -> repo root (used to show callers' paths
# relative to the repo instead of a bare module name, e.g.
# "scripts/monitor_bcm.py" instead of just "monitor_bcm").
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Binary frame protocol -------------------------------------------------
# Wire format: START(0x7E) TYPE(1) LEN(1) PAYLOAD(LEN) CRC16_LO CRC16_HI
# Must match firmware/BCM_Firmware/Core/Src/main.c exactly (frame types,
# struct layout, and CRC algorithm).
FRAME_START = 0x7E


class SerialLinkLost(Exception):
    """Raised when a frame can't be sent because the serial connection is
    closed or gone (dropped by the OS, port stolen by another process, cable
    unplugged, etc.) - callers can catch this specifically instead of
    getting a bare AttributeError from a None transport."""

CMD_SET_PEDAL = 0x01
CMD_SET_SPEED = 0x02
CMD_SET_TEMP = 0x03
CMD_RESET = 0x04
CMD_SET_WEAR = 0x05
CMD_GET_VERSION = 0x06

RESP_ACK = 0x10
RESP_NACK = 0x11
RESP_TELEMETRY = 0x20
RESP_VERSION = 0x21

CMD_NAMES = {
    CMD_SET_PEDAL: "SET_PEDAL",
    CMD_SET_SPEED: "SET_SPEED",
    CMD_SET_TEMP: "SET_TEMP",
    CMD_RESET: "RESET",
    CMD_SET_WEAR: "SET_WEAR",
    CMD_GET_VERSION: "GET_VERSION",
}

# tick(u32), pedal/speed/wear/front/rear(f32 x5), status_flag(u8), chip_temp_c(i32)
TELEMETRY_STRUCT = "<IfffffBi"

# status_flag bit layout, mirrors bcm/include/bcm_types.h exactly (bits 6-7
# are a free-running heartbeat counter, not a status bit - see bcm_diag.c).
FLAG_BRAKE_LIGHT = 0x01
FLAG_THERMAL_FAULT = 0x02
FLAG_ABS_ACTIVE = 0x04
FLAG_HSA_ACTIVE = 0x08
FLAG_PLAUS_FAULT = 0x10
FLAG_BRAKE_WEAR = 0x20

_FLAG_NAMES = (
    (FLAG_THERMAL_FAULT, "THERMAL_FAULT"),
    (FLAG_PLAUS_FAULT, "PLAUS_FAULT"),
    (FLAG_ABS_ACTIVE, "ABS_ACTIVE"),
    (FLAG_HSA_ACTIVE, "HSA_ACTIVE"),
    (FLAG_BRAKE_WEAR, "BRAKE_WEAR"),
    (FLAG_BRAKE_LIGHT, "BRAKE_LIGHT"),
)


def active_flag_names(flag: int) -> str:
    """Comma-joined names of the status bits set in `flag` (heartbeat bits excluded)."""
    names = [name for mask, name in _FLAG_NAMES if flag & mask]
    return ",".join(names) if names else "none"


# Bits that correspond to a physical actuation the BCM performs in response
# to input data, as opposed to a pure diagnostic/advisory bit (PLAUS_FAULT,
# BRAKE_WEAR - those have no distinct actuator output of their own, so they
# only show up via derive_system_state/Log.state_change, not here).
# mask -> (actuator name, label when the bit goes 1, label when it goes 0)
ACTUATOR_BITS = (
    (FLAG_BRAKE_LIGHT, "Brake light", "ON", "OFF"),
    (FLAG_ABS_ACTIVE, "ABS modulation", "ENGAGED", "RELEASED"),
    (FLAG_HSA_ACTIVE, "Hill Start Assist (pressure hold)", "ENGAGED", "RELEASED"),
    # Thermal fault has a direct physical effect (SWE_REQ_008: hydraulic
    # pressure gets clamped once latched), so it counts as an actuation too.
    (FLAG_THERMAL_FAULT, "Thermal safety clamp", "ENGAGED", "RELEASED"),
)


def derive_system_state(flag: int) -> str:
    """Collapses the raw status_flag byte into one of a small set of
    high-level system states, ordered by severity so exactly one applies:

        FAULT   - a latched safety fault is active (thermal or plausibility)
        WARNING - a non-critical advisory is active (brake wear)
        ACTIVE  - a safety feature is actively intervening (ABS or HSA)
        NORMAL  - none of the above

    This is a bridge-side view of what is otherwise a scattered bag of
    independent bits, so the state the system is "in" can be tracked and
    logged as a state machine instead of raw flag numbers.
    """
    if flag & (FLAG_THERMAL_FAULT | FLAG_PLAUS_FAULT):
        return "FAULT"
    if flag & FLAG_BRAKE_WEAR:
        return "WARNING"
    if flag & (FLAG_ABS_ACTIVE | FLAG_HSA_ACTIVE):
        return "ACTIVE"
    return "NORMAL"


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
    "TELEM": "\033[90m",
    "ERROR": "\033[31m",
    "STATE": "\033[1m\033[35m",
    "ACTUATOR": "\033[1m\033[36m",
}

# Human-readable description shown alongside a tag, e.g. "[TX : Command
# sent]" — only for tags whose meaning isn't already obvious (INFO/ERROR
# aren't here on purpose: they don't need explaining).
_TAG_DESCRIPTIONS = {
    "TX": "Command sent",
    "TELEM": "Telemetry sample",
    "VERBOSE": "Verbose output",
    "STAGE_START": "Stage start",
    "STAGE_END": "Stage end",
    "STATE": "System state transition",
    "ACTUATOR": "Actuator action",
}


def _tag_and_caller(record, tag):
    """Builds the shared "[TAG] [path/to/file.py function : name]" prefix used
    by both the console and file formatters, so a reader can tell at a glance
    what kind of event this is and exactly which function logged it. Tags in
    _TAG_DESCRIPTIONS get a ": description" suffix; self-explanatory ones
    (INFO, ERROR) don't. The path is relative to the repo root (e.g.
    "scripts/monitor_bcm.py"), not just the bare module name, so files with
    the same module name in different directories stay unambiguous."""
    description = _TAG_DESCRIPTIONS.get(tag)
    tag_part = f"[{tag} : {description}]" if description else f"[{tag}]"
    try:
        rel_path = os.path.relpath(record.pathname, _REPO_ROOT)
    except ValueError:
        rel_path = record.pathname
    return f"{tag_part} [{rel_path} function : {record.funcName}]"


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

        if tag == "STATE":
            return f"{color}\n{ts} {prefix} *** {message} ***\033[0m"
        if tag == "ACTUATOR":
            return f"{color}{ts} {prefix} >>> {message}\033[0m"

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

    @staticmethod
    def actuator(name, action, front=None, rear=None, pedal=None, speed=None, tick=None):
        # Always logged at INFO, same reasoning as state_change: an actuator
        # edge is a discrete, rare, meaningful event - it belongs on the
        # console, not buried in per-sample TELEM debug spam.
        tick_part = f" tick={tick}" if tick is not None else ""
        detail = (
            f" [front={front:.1f} bar rear={rear:.1f} bar pedal={pedal:.1f}% speed={speed:.1f}km/h]"
            if front is not None else ""
        )
        _logger.info(f"{name} -> {action}{tick_part}{detail}", extra={"tag": "ACTUATOR"}, stacklevel=2)

    @staticmethod
    def state_change(old_state, new_state, flag, tick=None):
        # Always logged at INFO (unlike the per-sample TELEM/debug spam), since
        # a state transition is rare and exactly the kind of event worth
        # seeing on the console without wading through raw telemetry.
        tick_part = f" tick={tick}" if tick is not None else ""
        _logger.info(
            f"{old_state} -> {new_state}{tick_part} [flag=0x{flag:02X} {active_flag_names(flag)}]",
            extra={"tag": "STATE"},
            stacklevel=2,
        )


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
        self.version_queue = queue.Queue()
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
        elif frame_type == RESP_VERSION:
            self.version_queue.put(payload.decode("ascii", errors="replace"))
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
                self.on_telemetry(d)  # pylint: disable=not-callable  # guarded by the `if`; pylint sees only the None init

    def write_frame(self, frame_type: int, payload: bytes = b""):
        if self.transport is None:
            raise SerialLinkLost(
                "Cannot send frame - serial connection is closed (lost or "
                "taken by another process). Check nothing else has the port "
                "open, then restart."
            )
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

        # Durable record of the system-state machine (see derive_system_state):
        # one row per transition, not per sample, so it stays readable even
        # over a long run.
        self.state_log_filename = os.path.join(HardwareBridge._session_dir, f"state_transitions_{time_suffix}.csv")
        self.state_log_file = open(self.state_log_filename, "w")
        self.state_log_file.write("Mac_Time,ECU_Tick,Old_State,New_State,Flags,Active_Flags\n")
        self.state_log_file.flush()
        self._system_state = None

        # Durable record of actuator edges (see ACTUATOR_BITS): one row per
        # physical action taken in response to input data, not per sample.
        self.actuator_log_filename = os.path.join(HardwareBridge._session_dir, f"actuator_events_{time_suffix}.csv")
        self.actuator_log_file = open(self.actuator_log_filename, "w")
        self.actuator_log_file.write("Mac_Time,ECU_Tick,Actuator,Action,Front_bar,Rear_bar,Pedal_pct,Speed_kmh\n")
        self.actuator_log_file.flush()
        self._prev_flag = None

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
        tick = d.get('t', 0)
        Log.debug(
            f"tick={tick} pedal={d.get('p', 0)} speed={d.get('s', 0)} "
            f"wear={d.get('w', 0)} front={d.get('f', 0)} rear={d.get('r', 0)} "
            f"lights={l_val} flag=0x{flag:02X} chip_c={d.get('chip_c', 0)}"
        )

        new_state = derive_system_state(flag)
        if new_state != self._system_state:
            old_state = self._system_state or "INITIAL"
            Log.state_change(old_state, new_state, flag, tick=tick)
            self.state_log_file.write(f"{ts},{tick},{old_state},{new_state},{flag},{active_flag_names(flag)}\n")
            self.state_log_file.flush()
            self._system_state = new_state

        if self._prev_flag is not None:
            changed_bits = flag ^ self._prev_flag
            for mask, name, on_label, off_label in ACTUATOR_BITS:
                if changed_bits & mask:
                    action = on_label if (flag & mask) else off_label
                    front, rear = d.get('f', 0), d.get('r', 0)
                    pedal, speed = d.get('p', 0), d.get('s', 0)
                    Log.actuator(name, action, front=front, rear=rear, pedal=pedal, speed=speed, tick=tick)
                    self.actuator_log_file.write(f"{ts},{tick},{name},{action},{front},{rear},{pedal},{speed}\n")
                    self.actuator_log_file.flush()
        self._prev_flag = flag

    def _send_command(self, frame_type: int, value: float = None):
        """Sends a framed command and waits for ACK/NACK from the background
        reader, logging the send and the result as a single line (rather
        than separate TX/RX lines) to keep command traffic readable over a
        long session."""
        payload = struct.pack("<f", value) if value is not None else b""
        name = CMD_NAMES.get(frame_type, f"0x{frame_type:02X}")
        label = f"{name}({value})" if value is not None else name

        # Clear queue of any stale ACKs
        while not self.protocol.response_queue.empty():
            self.protocol.response_queue.get()

        self.protocol.write_frame(frame_type, payload)

        # Wait for the reader to signal ACK/NACK reception
        try:
            response = self.protocol.response_queue.get(timeout=1.5)
            if response == RESP_ACK:
                Log.trace_tx(f"{label} -> ACK")
            else:
                Log.error(f"{label} -> NACK (bad CRC?)")
        except queue.Empty:
            Log.error(f"{label} -> timeout (No ACK)")

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

    def get_version(self):
        """Asks the board for the firmware version baked in at compile time
        (see CMD_GET_VERSION in main.c) and returns it as a string, e.g.
        "v1.0.0-HIL-VALIDATED-3-gA55fe14-dirty". Unlike a flash log, this
        reflects whatever is *actually running on the board right now* -
        useful for confirming a board wasn't left on stale firmware."""
        while not self.protocol.version_queue.empty():
            self.protocol.version_queue.get()

        self.protocol.write_frame(CMD_GET_VERSION)

        try:
            version = self.protocol.version_queue.get(timeout=1.5)
            Log.trace_tx(f"GET_VERSION -> {version}")
            return version
        except queue.Empty:
            Log.error("GET_VERSION -> timeout (no response)")
            return None

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

        if hasattr(self, "state_log_file") and self.state_log_file:
            self.state_log_file.close()

        if hasattr(self, "actuator_log_file") and self.actuator_log_file:
            self.actuator_log_file.close()
