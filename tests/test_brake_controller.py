import pytest
import can
import time

# ---------------------------------------------------------------------------
# CAN message constants
# ---------------------------------------------------------------------------
BRAKE_CMD_ID = 0x200  # input: brake pedal position
TEMP_CMD_ID = 0x220  # input: brake temperature
WEAR_CMD_ID = 0x240  # input: brake pad wear
SPEED_CMD_ID = 0x210  # input: vehicle speed
PRESSURE_RESP_ID = 0x300  # output: brake pressure response
ABS_STATUS_ID = 0x400  # output: ABS / Overheat / Wear flags

MAX_PEDAL_VALID = 0x64  # 100%
PEDAL_OVER_BY_ONE = 0x65
PEDAL_150PCT = 0x96
PEDAL_MAX_BYTE = 0xFF

ABS_BIT = 0x01
OVERHEAT_BIT = 0x02
WEAR_BIT = 0x08

RECV_TIMEOUT = 1.0
FLUSH_TIMEOUT = 0.01


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def flush(can_bus):
    """Drain stale messages."""
    while can_bus.recv(timeout=0):
        pass


def recv_id(can_bus, arb_id, timeout=RECV_TIMEOUT):
    """Block until a message with the given arbitration ID arrives or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = can_bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == arb_id:
            return msg
    return None


def send_brake(can_bus, pedal, extended=False):
    can_bus.send(
        can.Message(
            arbitration_id=BRAKE_CMD_ID,
            data=[0x00, 0x00, 0x00, pedal],
            is_extended_id=extended,
        )
    )


def send_speed(can_bus, speed):
    can_bus.send(
        can.Message(
            arbitration_id=SPEED_CMD_ID,
            data=[0x00, 0x00, speed],
            is_extended_id=False,
        )
    )


def send_temp(can_bus, temp):
    can_bus.send(
        can.Message(
            arbitration_id=TEMP_CMD_ID,
            data=[temp],
            is_extended_id=False,
        )
    )


def send_wear(can_bus, wear):
    can_bus.send(
        can.Message(
            arbitration_id=WEAR_CMD_ID,
            data=[wear],
            is_extended_id=False,
        )
    )


# ===========================================================================
# 1. PEDAL BOUNDARY TESTS
# ===========================================================================


class TestPedalBoundary:
    """Verify the ECU handles every boundary of the pedal range correctly."""

    def test_zero_pedal(self, can_bus, ecu_reset):
        """0x00 input: ECU must respond with zero pressure."""
        flush(can_bus)
        send_brake(can_bus, 0x00)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to zero-pedal input"
        assert resp.data[3] == 0x00, f"Expected 0 pressure, got {resp.data[3]:#x}"

    def test_exact_max(self, can_bus, ecu_reset):
        """0x64 (100%): maximum valid value — must not be clamped or rejected."""
        flush(can_bus)
        send_brake(can_bus, MAX_PEDAL_VALID)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to 100% pedal"
        assert (
            resp.data[3] == MAX_PEDAL_VALID
        ), f"Expected {MAX_PEDAL_VALID:#x}, got {resp.data[3]:#x}"

    def test_one_above_max(self, can_bus, ecu_reset):
        """0x65 (just over limit): ECU must clamp to 0x64."""
        flush(can_bus)
        send_brake(can_bus, PEDAL_OVER_BY_ONE)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to 0x65 pedal"
        assert (
            resp.data[3] <= MAX_PEDAL_VALID
        ), f"ECU passed 0x65 unclamped: got {resp.data[3]:#x}"


# ===========================================================================
# 2. STATUS FLAGS (ABS, OVERHEAT, WEAR)
# ===========================================================================


class TestStatusFlags:
    """Verify ABS, Overheat, and Wear flags are set correctly in the status byte."""

    @pytest.mark.parametrize(
        "speed,pedal,expected_abs",
        [
            (120, 90, 1),  # high speed + hard brake  → ON
            (30, 90, 0),  # low speed  + hard brake  → OFF
            (120, 20, 0),  # high speed + light brake → OFF
        ],
    )
    def test_abs_logic(self, can_bus, ecu_reset, speed, pedal, expected_abs):
        flush(can_bus)
        send_speed(can_bus, speed)
        time.sleep(0.1)
        send_brake(can_bus, pedal)
        status = recv_id(can_bus, ABS_STATUS_ID, timeout=2.0)
        assert status is not None, f"No status for speed={speed}, pedal={pedal}"
        actual = status.data[0] & ABS_BIT
        assert actual == expected_abs

    def test_brake_overheat_warning(self, can_bus, ecu_reset):
        """Verify Brake Overheat flag is set when temperature > 200°C."""
        flush(can_bus)
        send_temp(can_bus, 250)
        time.sleep(0.1)
        send_brake(can_bus, 0x32)  # trigger status update
        status = recv_id(can_bus, ABS_STATUS_ID, timeout=2.0)
        assert status is not None, "ECU did not send status!"
        assert (
            status.data[0] & OVERHEAT_BIT
        ), f"Expected Overheat flag, got {status.data[0]:#x}"

    def test_brake_wear_warning(self, can_bus, ecu_reset):
        """Verify Brake Wear flag is set when wear > 90%."""
        flush(can_bus)
        send_wear(can_bus, 95)
        time.sleep(0.1)
        send_brake(can_bus, 0x32)  # trigger status update
        status = recv_id(can_bus, ABS_STATUS_ID, timeout=2.0)
        assert status is not None, "ECU did not send status!"
        assert status.data[0] & WEAR_BIT, f"Expected Wear flag, got {status.data[0]:#x}"
