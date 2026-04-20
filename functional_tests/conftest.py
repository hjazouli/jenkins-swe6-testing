import os
import threading
import time
from typing import List

import can
import pytest


# -----------------------------------------------------------------------------
# 1. VIRTUAL ECU SIMULATOR
# -----------------------------------------------------------------------------


class VirtualECU(threading.Thread):
    """
    Simulates a brake ECU (e.g. TC397) on the CAN bus.
    Runs in a background thread and processes incoming brake/speed signals.
    """

    def __init__(self, bus: can.BusABC):
        super().__init__()
        self.bus = bus
        self.running = True
        self.daemon = True
        self.vehicle_speed = 0
        self.brake_temp = 0
        self.brake_wear = 0

    def run(self):
        print("\n[Virtual ECU] Initialized and listening on CAN bus...")
        while self.running:
            # Process all pending messages
            while True:
                msg = self.bus.recv(timeout=0.01)
                if not msg:
                    break
                self.process_message(msg)
            time.sleep(0.01)

    def process_message(self, msg: can.Message):
        # 0x210: Vehicle Speed
        if msg.arbitration_id == 0x210:
            self.vehicle_speed = msg.data[2]
            print(f"[Virtual ECU] Updated VehSpeed: {self.vehicle_speed} km/h")

        # 0x220: Brake Temperature
        elif msg.arbitration_id == 0x220:
            self.brake_temp = msg.data[0]
            print(f"[Virtual ECU] Updated BrakeTemp: {self.brake_temp} C")

        # 0x240: Brake Pad Wear (SWE_REQ_006)
        elif msg.arbitration_id == 0x240:
            self.brake_wear = msg.data[0]
            print(f"[Virtual ECU] Updated BrakeWear: {self.brake_wear}%")

        # 0x100: ECU Reset / Diagnostic Command
        elif msg.arbitration_id == 0x100:
            # Check for reset subfunction
            if msg.data[1] == 0x11:
                print("[Virtual ECU] Resetting state...")
                self.vehicle_speed = 0
                self.brake_temp = 0
                self.brake_wear = 0
            # Check for diagnostic session control
            elif msg.data[0] == 0x10:
                sub_fn = msg.data[1]
                print(f"[Virtual ECU] Diagnostic Session Switch: 0x{sub_fn:02x}")
                # Positive response (SID + 0x40)
                resp = can.Message(
                    arbitration_id=0x700, data=[0x50, sub_fn], is_extended_id=False
                )
                self.bus.send(resp)

        # 0x200: Brake Pedal Message
        elif msg.arbitration_id == 0x200:
            pedal_value = msg.data[3]

            # SWE_REQ_003: Cap out-of-bounds pedal values to 100%
            if pedal_value > 100:
                pedal_value = 100

            print(f"[Virtual ECU] Received Brake Pedal: {pedal_value}%")

            # Simulate ECU calculating Hydraulic pressure (1:1 mapping for simplicity)
            # Response goes to 0x300
            response = can.Message(
                arbitration_id=0x300,
                data=[0x00, 0x00, 0x00, pedal_value],
                is_extended_id=False,
            )
            self.bus.send(response)

            # Simulate ABS Status logic
            # If speed > 100 AND brake > 80% -> Activate ABS (Bit 0 of status)
            abs_active = (
                0x01 if (self.vehicle_speed > 100 and pedal_value > 80) else 0x00
            )

            # Brake Overheat logic (Bit 1)
            overheat_active = 0x02 if self.brake_temp > 200 else 0x00

            # Brake Wear logic (Bit 3)
            wear_warning = 0x08 if self.brake_wear > 90 else 0x00

            status_msg = can.Message(
                arbitration_id=0x400,  # Status ID
                data=[abs_active | overheat_active | wear_warning, 0x00],
                is_extended_id=False,
            )
            self.bus.send(status_msg)

    def stop(self):
        self.running = False


# -----------------------------------------------------------------------------
# 2. HIL INFRASTRUCTURE MOCKS
# -----------------------------------------------------------------------------


class FaultInjectionController:
    """Mocks a physical relay/matrix board for Fault Injection (FI)."""

    FAULT_NONE = "NONE"
    FAULT_SHORT_GND = "SHORT_TO_GROUND"
    FAULT_SHORT_VBATT = "SHORT_TO_VBATT"
    FAULT_OPEN_CIRCUIT = "OPEN_CIRCUIT"

    def __init__(self):
        self.active_fault = self.FAULT_NONE

    def inject(self, channel: str, fault_type: str):
        print(f"[HIL FI] Injecting {fault_type} on {channel}")
        self.active_fault = fault_type

    def clear(self, channel: str):
        print(f"[HIL FI] Clearing faults on {channel}")
        self.active_fault = self.FAULT_NONE


class BenchPowerSupply:
    """Mocks a programmable power supply (e.g. R&S NGE100)."""

    NOMINAL_VOLTAGE = 12.0
    MIN_VOLTAGE = 9.0
    MAX_VOLTAGE = 16.0

    def __init__(self):
        self.voltage = self.NOMINAL_VOLTAGE
        self.is_on = True

    def set_voltage(self, voltage: float):
        if not (self.MIN_VOLTAGE <= voltage <= self.MAX_VOLTAGE):
            raise ValueError(
                f"Voltage {voltage}V is outside safe range {self.MIN_VOLTAGE}-{self.MAX_VOLTAGE}V"
            )
        print(f"[HIL PSU] Voltage set to {voltage}V")
        self.voltage = voltage

    def power_cycle(self, off_duration_s=0.5):
        print("[HIL PSU] Starting power cycle...")
        self.is_on = False
        time.sleep(off_duration_s)
        self.is_on = True
        print("[HIL PSU] Power cycle complete. Output ENABLED.")


class SignalMonitor:
    """Mocks a DAQ (Data Acquisition) system for monitoring analog signals."""

    def __init__(self):
        self.history = {}

    def sample(self, channel: str, mock_value: float) -> float:
        """Sample a channel and return its current voltage."""
        if channel not in self.history:
            self.history[channel] = []
        self.history[channel].append(mock_value)
        return mock_value

    def get_history(self, channel: str) -> List[float]:
        return self.history.get(channel, [])

    def assert_in_range(self, channel: str, low: float, high: float):
        """Assert every recorded sample for a channel is within [low, high] V."""
        history = self.get_history(channel)
        assert history, f"No samples recorded for channel '{channel}'"
        out_of_range = [v for v in history if not (low <= v <= high)]
        assert not out_of_range, (
            f"[DAQ] {channel}: {len(out_of_range)} sample(s) out of range "
            f"{out_of_range} (expected [{low}V, {high}V])"
        )


import serial
import time

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 9600


class HardwareBridge:
    def __init__(self):
        print(f"Hardware Bridge: Connecting to Hardware on {SERIAL_PORT}...")
        self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        self.serial.reset_input_buffer()

    def set_pedal(self, force: float):
        self.serial.write(f"P{force}\n".encode("utf-8"))

    def set_temp(self, temp: float):
        self.serial.write(f"T{temp}\n".encode("utf-8"))

    def set_speed(self, speed: float):
        self.serial.write(f"S{speed}\n".encode("utf-8"))

    def get_status(self):
        return self.serial.readline().decode("utf-8", errors="ignore").strip()

    def close(self):
        self.serial.close()


class SimBridge:
    def __init__(self, bcm_dll):
        self.bcm = bcm_dll
        self.input_struct = self.bcm.BcmInput_t()
        self.output_struct = self.bcm.BcmOutput_t()

    def set_pedal(self, force: float):
        self.input_struct.pedal_force = force
        self.output_struct.hydraulic_pressure = force / 10.0
        self._step()

    def set_temp(self, temp: float):
        self.input_struct.brake_temp_celsius = temp
        self._step()

    def set_speed(self, speed: float):
        self.input_struct.vehicle_speed = speed
        self._step()

    def _step(self):
        self.bcm.BCM_Safety_Check(self.bcm.ctypes.byref(self.input_struct), self.bcm.ctypes.byref(self.output_struct))
        self.bcm.BCM_Ebd_PerformSplit(self.bcm.ctypes.byref(self.input_struct), self.bcm.ctypes.byref(self.output_struct))

    def get_status(self) -> str:
        pedal_str = "DEPRESSED" if self.input_struct.pedal_force > 0.1 else "IDLE"
        brake_str = "ACTIVE" if (self.output_struct.status_flag & 0x01) else "INACTIVE"
        if self.input_struct.pedal_force > 0.1:
            return f"[BCM] Pedal: {pedal_str} | Lights: {brake_str} | F: {int(self.output_struct.front_hydraulic_pressure)} | R: {int(self.output_struct.rear_hydraulic_pressure)}"
        return f"[BCM] Status: IDLE | FLAG: {self.output_struct.status_flag}"

    def close(self):
        pass


# -----------------------------------------------------------------------------
# 3. PYTEST FIXTURES (The HIL Framework)
# -----------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--target", action="store", default="sim", help="Target: sim or hardware"
    )


@pytest.fixture
def bcm_target(request):
    target_type = request.config.getoption("--target")
    
    if target_type == "hardware":
        bridge = HardwareBridge()
        yield bridge
        bridge.close()
    else:
        # Return a simple mock or the SimBridge (we'll connect CAN later)
        yield SimBridge(None)


@pytest.fixture(scope="session")
def can_bus():
    """Initialize Virtual CAN interface."""
    # Test bus instance
    bus = can.interface.Bus(channel="vbus_shared", interface="virtual")
    # Separate bus instance for the ECU
    ecu_bus = can.interface.Bus(channel="vbus_shared", interface="virtual")

    # Start the Virtual ECU in the background
    ecu = VirtualECU(ecu_bus)
    ecu.start()

    yield bus

    ecu.stop()
    bus.shutdown()
    ecu_bus.shutdown()
    print("\n[Virtual ECU] Shutdown.")


@pytest.fixture
def ecu_reset(can_bus):
    """Simulate a reset via UDS diagnostic message."""
    reset_msg = can.Message(
        arbitration_id=0x100, data=[0x02, 0x11, 0x01], is_extended_id=False
    )
    can_bus.send(reset_msg)
    time.sleep(0.1)  # Simulate boot time


@pytest.fixture
def uds_session(can_bus):
    """Manage a UDS diagnostic session (setup = Extended, teardown = Default)."""
    # 1. Open Extended Session (0x10 0x03)
    can_bus.send(
        can.Message(arbitration_id=0x100, data=[0x10, 0x03], is_extended_id=False)
    )
    time.sleep(0.05)
    print("\n[UDS] Switched to EXTENDED SESSION (0x03)")

    yield "EXTENDED"

    # 2. Return to Default Session (0x10 0x01)
    can_bus.send(
        can.Message(arbitration_id=0x100, data=[0x10, 0x01], is_extended_id=False)
    )
    time.sleep(0.05)
    print("[UDS] Switched to DEFAULT SESSION (0x01)")


@pytest.fixture
def can_logger(can_bus, request):
    """Log CAN traffic to an .asc file named after the current test."""
    test_name = request.node.name
    log_file = f"capture_{test_name}.asc"

    # Simple mock: just yield the path
    # In a real HIL, we would attach a can.asc.ASCWriter
    yield log_file

    if os.path.exists(log_file):
        print(f"[LOG] CAN Capture saved to {log_file}")


@pytest.fixture
def fault_injection():
    """Provide a FaultInjectionController instance."""
    fi = FaultInjectionController()
    yield fi
    fi.clear("ALL")  # Safety teardown: ensure all relays are open


@pytest.fixture
def power_supply():
    """Provide a BenchPowerSupply instance."""
    psu = BenchPowerSupply()
    yield psu
    psu.set_voltage(BenchPowerSupply.NOMINAL_VOLTAGE)  # Safety teardown


@pytest.fixture
def signal_monitor():
    """Provide a SignalMonitor (DAQ) instance."""
    monitor = SignalMonitor()
    yield monitor
