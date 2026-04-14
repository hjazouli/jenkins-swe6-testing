import pytest
import can
import time
import cantools
import os

# ==============================================================================
# CONFIGURATION & CAN LOADERS
# ==============================================================================

DBC_PATH = os.path.join(os.path.dirname(__file__), "..", "bcm_matrix.dbc")
db = cantools.database.load_file(DBC_PATH)

# Message Identifiers
BRAKE_CMD = 0x200  # Brake command
SPEED_CMD = 0x210  # Vehicle speed
PRESS_RESP = 0x300  # Pressure response
STATUS_RESP = 0x400  # Status response

# ==============================================================================
# CAN BUS HELPERS
# ==============================================================================


def transmit_brake_command(bus, pedal_pct, volt_mv=2500):
    """Transmits brake pedal command signals over CAN."""
    data = db.encode_message(
        "BRAKE_CMD", {"Pedal_Force": pedal_pct, "Pedal_Voltage": volt_mv}
    )
    bus.send(can.Message(arbitration_id=BRAKE_CMD, data=data))


def transmit_vehicle_dynamics(bus, speed, rain=False, decel_ms2=0):
    """Transmits vehicle environment and dynamics signals."""
    data = db.encode_message(
        "VEH_SPEED",
        {
            "Vehicle_Speed": speed,
            "Rain_Sensor": 1 if rain else 0,
            "Deceleration": decel_ms2,
        },
    )
    bus.send(can.Message(arbitration_id=SPEED_CMD, data=data))


def transmit_brake_temperature(bus, temp_c):
    """Transmits brake component temperature signal."""
    data = db.encode_message("BRAKE_TEMP", {"Brake_Temperature": temp_c})
    bus.send(can.Message(arbitration_id=0x220, data=data))


def receive_can_message(bus, arb_id, timeout=1.0):
    """Awaits and returns a specific CAN frame from the bus."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == arb_id:
            return msg
    return None


# ==============================================================================
# SECTION 1: CORE DYNAMICS & CONTROL (ABS / EBD)
# ==============================================================================


@pytest.mark.usefixtures("ecu_reset")
class TestVehicleDynamics:
    """Verifies braking behavior under high-speed and deceleration conditions."""

    def test_abs_reduction(self, can_bus):
        """Verify ABS proportional reduction (0.62 factor) at high vehicle speeds."""
        transmit_vehicle_dynamics(can_bus, 120, rain=False, decel_ms2=0)
        transmit_brake_command(can_bus, 100, volt_mv=2500)

        msg = receive_can_message(can_bus, PRESS_RESP)
        assert msg is not None
        signals = db.decode_message("PRESSURE_FB", msg.data)
        assert signals["Front_Pressure"] == int(100 * 0.62)

    def test_ebd_control(self, can_bus):
        """Verify EBD rear axle pressure limiting during high deceleration events."""
        # Initial state: fast but constant speed
        transmit_vehicle_dynamics(can_bus, 81, rain=False)
        transmit_brake_command(can_bus, 0)
        receive_can_message(can_bus, PRESS_RESP)

        # Trigger deceleration: 81 -> 80 km/h in 10ms is > 5m/s^2
        transmit_vehicle_dynamics(can_bus, 80, rain=False)
        transmit_brake_command(can_bus, 100)

        msg = receive_can_message(can_bus, PRESS_RESP)
        assert msg is not None
        signals = db.decode_message("PRESSURE_FB", msg.data)

        assert signals["Front_Pressure"] == 100
        assert signals["Rear_Pressure"] == 70


# ==============================================================================
# SECTION 2: ADAS FEATURES & THERMAL MANAGEMENT
# ==============================================================================


@pytest.mark.usefixtures("ecu_reset")
class TestSpecialFunctions:
    """Verifies environmental and safety-limiting features."""

    def test_overheat_clamping(self, can_bus):
        """Verify pressure is saturated to 50 Bar during a thermal overheat event."""
        transmit_brake_temperature(can_bus, 250)
        time.sleep(0.1)

        transmit_brake_command(can_bus, pedal_pct=100)

        msg = receive_can_message(can_bus, PRESS_RESP)
        assert msg is not None
        signals = db.decode_message("PRESSURE_FB", msg.data)
        assert signals["Front_Pressure"] == 50

    def test_wiping_priority(self, can_bus):
        """Verify driver braking input overrides ADAS Disc Wiping pressure (2 Bar)."""
        # Enable rain and speed to trigger wiping
        transmit_vehicle_dynamics(can_bus, 60, rain=True)
        time.sleep(2.0)

        # Driver applies 10% force
        transmit_brake_command(can_bus, 10)

        msg = receive_can_message(can_bus, PRESS_RESP)
        signals = db.decode_message("PRESSURE_FB", msg.data)
        assert signals["Front_Pressure"] == 10

    def test_thermal_hysteresis(self, can_bus):
        """Verify that the latching mechanism prevents rapid on/off cycling during marginal temperature conditions."""
        # 1. Induce Overheat (Set latch)
        transmit_brake_temperature(can_bus, 210)
        transmit_brake_command(can_bus, 60)
        msg = receive_can_message(can_bus, STATUS_RESP)
        signals = db.decode_message("STATUS_FB", msg.data)
        assert signals["Overheat_Flag"] == 1

        # 3. Reduce Temperature (Verify recovery delay)
        for _ in range(2):
            transmit_brake_temperature(can_bus, 190)
            transmit_brake_command(can_bus, 0)
            msg = receive_can_message(can_bus, STATUS_RESP)
            signals = db.decode_message("STATUS_FB", msg.data)
            assert signals["Overheat_Flag"] == 1

        # 4. Reduce Temperature below threshold (Clear latch)
        transmit_brake_temperature(can_bus, 180)
        transmit_brake_command(can_bus, 0)
        msg = receive_can_message(can_bus, STATUS_RESP)
        signals = db.decode_message("STATUS_FB", msg.data)
        assert signals["Overheat_Flag"] == 0


# ==============================================================================
# SECTION 3: SAFETY, DIAGNOSTICS & SIGNAL QUALITY
# ==============================================================================


@pytest.mark.safety
@pytest.mark.usefixtures("ecu_reset")
class TestSystemSafety:
    """Rigorous verification of Fail-Safe triggers and signal plausibility."""

    def test_failsafe_activation(self, can_bus):
        """Verify system enters Fail-Safe (0 Bar) upon electrical sensor fault."""
        transmit_brake_command(can_bus, pedal_pct=50, volt_mv=200)

        msg_p = receive_can_message(can_bus, PRESS_RESP)
        assert msg_p is not None
        press = db.decode_message("PRESSURE_FB", msg_p.data)
        assert press["Front_Pressure"] == 0

        msg_s = receive_can_message(can_bus, STATUS_RESP)
        assert msg_s is not None
        status = db.decode_message("STATUS_FB", msg_s.data)
        assert status["FailSafe_Flag"] == 1

    @pytest.mark.parametrize("invalid_volt", [200, 4800, 0, 5000])
    def test_signal_quality_range(self, can_bus, invalid_volt):
        """Verify Fail-Safe activation across the full invalid voltage spectrum."""
        transmit_brake_command(can_bus, pedal_pct=50, volt_mv=invalid_volt)

        msg_p = receive_can_message(can_bus, PRESS_RESP)
        assert msg_p is not None
        assert db.decode_message("PRESSURE_FB", msg_p.data)["Front_Pressure"] == 0

        msg_s = receive_can_message(can_bus, STATUS_RESP)
        assert msg_s is not None
        assert db.decode_message("STATUS_FB", msg_s.data)["FailSafe_Flag"] == 1


# ==============================================================================
# SECTION 4:
# ==============================================================================


@pytest.mark.usefixtures("ecu_reset")
class TestSystemSafety:
    def test_plausibility_check(self, can_bus):
        """Verify the detection of stuck pedal or mechanical failure, and accessing fail-safe."""

        for i in range(7):
            # Simulate constant speed (no deceleration)
            transmit_vehicle_dynamics(can_bus, 60, rain=False)
            # Apply 80% pedal force (high force, no deceleration = plausible failure)
            transmit_brake_command(can_bus, 80)

            # Receive and decode inside the loop to watch the flag change in real-time
            msg = receive_can_message(can_bus, STATUS_RESP)
            if msg:
                signals = db.decode_message("STATUS_FB", msg.data)
                # You can now watch signals["FailSafe_Flag"] here
            else:
                pytest.fail("Timeout waiting for STATUS_RESP")

        assert signals["FailSafe_Flag"] == 1
