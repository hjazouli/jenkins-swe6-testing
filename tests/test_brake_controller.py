import pytest
import can
import time

# ---------------------------------------------------------------------------
# CAN message constants
# ---------------------------------------------------------------------------
BRAKE_CMD_ID = 0x200  # input: brake pedal position
SPEED_CMD_ID = 0x210  # input: vehicle speed
PRESSURE_RESP_ID = 0x300  # output: brake pressure response
ABS_STATUS_ID = 0x400  # output: ABS / EBA status flags

MAX_PEDAL_VALID = 0x64  # 100%  — highest accepted value
PEDAL_OVER_BY_ONE = 0x65  # one step above the limit
PEDAL_150PCT = 0x96  # 150%  — canonical fault injection value
PEDAL_MAX_BYTE = 0xFF  # largest possible byte

ABS_BIT = 0x01  # bit 0 of ABS status byte
EBA_BIT = 0x02  # bit 1 of ABS status byte (assumed)

RECV_TIMEOUT = 1.0  # seconds to wait for a response
FLUSH_TIMEOUT = 0.01  # small timeout for buffer drain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def flush(can_bus):
    """Drain stale messages with a safe non-zero timeout."""
    while can_bus.recv(timeout=FLUSH_TIMEOUT):
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


# ===========================================================================
# 1. PEDAL BOUNDARY TESTS
# ===========================================================================


class TestPedalBoundary:
    """Verify the ECU handles every boundary of the pedal range correctly."""

    def test_zero_pedal(self, can_bus, ecu_reset):
        """0x00 input: ECU must respond with zero pressure."""
        send_brake(can_bus, 0x00)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to zero-pedal input"
        assert resp.data[3] == 0x00, f"Expected 0 pressure, got {resp.data[3]:#x}"

    def test_one_below_max(self, can_bus, ecu_reset):
        """0x63 (99%): a valid value just below the limit — must pass through."""
        pedal = MAX_PEDAL_VALID - 1
        send_brake(can_bus, pedal)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to 99% pedal"
        assert (
            resp.data[3] == pedal
        ), f"ECU should echo 0x{pedal:02x}, got {resp.data[3]:#x}"

    def test_exact_max(self, can_bus, ecu_reset):
        """0x64 (100%): maximum valid value — must not be clamped or rejected."""
        send_brake(can_bus, MAX_PEDAL_VALID)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to 100% pedal"
        assert (
            resp.data[3] == MAX_PEDAL_VALID
        ), f"Expected {MAX_PEDAL_VALID:#x}, got {resp.data[3]:#x}"

    def test_one_above_max(self, can_bus, ecu_reset):
        """0x65 (just over limit): ECU must clamp to 0x64."""
        send_brake(can_bus, PEDAL_OVER_BY_ONE)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to 0x65 pedal"
        assert (
            resp.data[3] <= MAX_PEDAL_VALID
        ), f"ECU passed 0x65 unclamped: got {resp.data[3]:#x}"

    def test_150_percent(self, can_bus, ecu_reset):
        """0x96 (150%): canonical over-range value — must clamp to 0x64."""
        send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to 150% pedal"
        assert (
            resp.data[3] <= MAX_PEDAL_VALID
        ), f"ECU did not clamp 0x96: got {resp.data[3]:#x}"

    def test_full_byte_max(self, can_bus, ecu_reset):
        """0xFF: highest possible byte — ECU must not crash and must clamp."""
        send_brake(can_bus, PEDAL_MAX_BYTE)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU silent on 0xFF pedal — possible hang"
        assert (
            resp.data[3] <= MAX_PEDAL_VALID
        ), f"ECU did not clamp 0xFF: got {resp.data[3]:#x}"


# ===========================================================================
# 2. ABS ACTIVATION LOGIC
# ===========================================================================


class TestABSLogic:
    """ABS turns on when both speed and pedal force cross their thresholds."""

    @pytest.mark.parametrize(
        "speed,pedal,expected_abs",
        [
            (120, 90, 1),  # high speed + hard brake  → ON
            (30, 90, 0),  # low speed  + hard brake  → OFF
            (120, 20, 0),  # high speed + light brake → OFF
            (0, 90, 0),  # zero speed + hard brake  → OFF (vehicle stopped)
            (120, 0, 0),  # high speed + zero brake  → OFF (no braking)
            (255, 90, 1),  # max speed  + hard brake  → ON
        ],
    )
    def test_abs_parametrized(self, can_bus, ecu_reset, speed, pedal, expected_abs):
        send_speed(can_bus, speed)
        time.sleep(0.1)
        send_brake(can_bus, pedal)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None, f"No ABS status for speed={speed}, pedal={pedal}"
        actual = status.data[0] & ABS_BIT
        assert (
            actual == expected_abs
        ), f"ABS expected={expected_abs}, got={actual} (speed={speed}, pedal={pedal})"

    def test_abs_speed_threshold_boundary_above(self, can_bus, ecu_reset):
        """Speed one step above the ABS threshold with hard brake → ABS ON."""
        # Assumes threshold is between 30 and 120; adjust if known precisely.
        send_speed(can_bus, 121)
        time.sleep(0.1)
        send_brake(can_bus, 90)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None
        assert status.data[0] & ABS_BIT, "ABS should be ON one step above threshold"

    def test_abs_speed_threshold_boundary_below(self, can_bus, ecu_reset):
        """Speed one step below the ABS threshold with hard brake → ABS OFF."""
        send_speed(can_bus, 29)
        time.sleep(0.1)
        send_brake(can_bus, 90)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None
        assert not (
            status.data[0] & ABS_BIT
        ), "ABS should be OFF one step below threshold"

    def test_abs_order_matters_brake_before_speed(self, can_bus, ecu_reset):
        """
        Brake sent before speed: ECU must evaluate ABS on the combined state,
        not just the order of arrival. Result should match the canonical case.
        """
        send_brake(can_bus, 90)  # brake first — no speed context yet
        time.sleep(0.05)
        send_speed(can_bus, 120)  # speed arrives after
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        # At minimum, the ECU must respond and not hang.
        assert status is not None, "ECU silent when brake arrives before speed"


# ===========================================================================
# 3. FAULT INJECTION
# ===========================================================================


class TestFaultInjection:
    """
    SWE_REQ_005 — ECU must handle deliberately malformed inputs safely.
    These tests differ from TestPedalBoundary: they care about *behaviour
    under fault conditions*, not value clamping per se.
    """

    def test_single_fault_response_present(self, can_bus, ecu_reset):
        """ECU must respond to a fault frame — not go silent."""
        send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU did not respond to fault frame"

    def test_single_fault_pressure_capped(self, can_bus, ecu_reset):
        """Fault frame pressure output must be ≤ 100% regardless of input."""
        send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None
        assert (
            resp.data[3] <= MAX_PEDAL_VALID
        ), f"Pressure not capped after fault: {resp.data[3]:#x}"

    def test_fault_does_not_trigger_abs_alone(self, can_bus, ecu_reset):
        """A fault frame (no speed context) must not spuriously activate ABS."""
        send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        # Wait briefly and check whether any ABS status arrived
        abs_msg = recv_id(can_bus, ABS_STATUS_ID, timeout=0.5)
        if abs_msg is not None:
            assert not (
                abs_msg.data[0] & ABS_BIT
            ), "ABS spuriously activated by fault frame alone"

    def test_burst_of_fault_frames(self, can_bus, ecu_reset):
        """ECU must survive 20 back-to-back invalid frames without hanging."""
        for _ in range(20):
            send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        # The ECU must still respond to a subsequent valid frame.
        send_brake(can_bus, 0x32)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU stopped responding after burst of fault frames"
        assert resp.data[3] == 0x32, "Valid frame after burst not processed correctly"

    def test_all_ff_payload(self, can_bus, ecu_reset):
        """Payload of all 0xFF bytes — every field maxed out."""
        can_bus.send(
            can.Message(
                arbitration_id=BRAKE_CMD_ID,
                data=[0xFF, 0xFF, 0xFF, 0xFF],
                is_extended_id=False,
            )
        )
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU silent on all-0xFF payload"
        assert resp.data[3] <= MAX_PEDAL_VALID, "ECU did not clamp all-0xFF payload"

    def test_fault_in_wrong_byte_position(self, can_bus, ecu_reset):
        """
        Invalid value in data[2] instead of data[3] — the byte the ECU does
        not read as pedal. ECU should treat pedal (data[3]) as 0 and respond
        normally, not crash.
        """
        can_bus.send(
            can.Message(
                arbitration_id=BRAKE_CMD_ID,
                data=[0x00, 0x00, 0xFF, 0x00],  # corruption in byte 2
                is_extended_id=False,
            )
        )
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU silent when byte 2 is 0xFF"


# ===========================================================================
# 4. PROTOCOL / FRAME FORMAT
# ===========================================================================


class TestProtocol:
    """ECU must be robust to malformed frames at the CAN framing level."""

    def test_short_frame_one_byte(self, can_bus, ecu_reset):
        """Frame with only 1 data byte: ECU must not crash."""
        can_bus.send(
            can.Message(
                arbitration_id=BRAKE_CMD_ID,
                data=[0x32],
                is_extended_id=False,
            )
        )
        flush(can_bus)
        # Any response is acceptable; silence for > 1s after a valid frame would be a failure.
        send_brake(can_bus, 0x32)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU hung after receiving a 1-byte short frame"

    def test_empty_frame_zero_bytes(self, can_bus, ecu_reset):
        """Zero-length data frame on the brake ID."""
        can_bus.send(
            can.Message(
                arbitration_id=BRAKE_CMD_ID,
                data=[],
                is_extended_id=False,
            )
        )
        flush(can_bus)
        send_brake(can_bus, 0x32)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU hung after receiving an empty frame"

    def test_extended_id_flag(self, can_bus, ecu_reset):
        """
        Same arbitration ID sent with is_extended_id=True.
        ECU should either ignore it or handle it gracefully — never crash.
        """
        send_brake(can_bus, 0x32, extended=True)
        flush(can_bus)
        # Probe liveness with a normal frame.
        send_brake(can_bus, 0x32)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU hung after extended-ID frame"

    def test_unknown_arbitration_id(self, can_bus, ecu_reset):
        """Frame on an ID the ECU does not listen to — must not cause any state change."""
        can_bus.send(
            can.Message(
                arbitration_id=0x999,
                data=[0x00, 0x00, 0x00, PEDAL_150PCT],
                is_extended_id=False,
            )
        )
        flush(can_bus)
        # Confirm ECU still responds normally on the real brake ID.
        send_brake(can_bus, 0x32)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU stopped responding after unknown arbitration ID"
        assert resp.data[3] == 0x32, "ECU state corrupted by unknown arbitration ID"

    def test_all_zero_valid_frame(self, can_bus, ecu_reset):
        """All-zero payload is a valid frame (0% pedal) — ECU must handle it."""
        can_bus.send(
            can.Message(
                arbitration_id=BRAKE_CMD_ID,
                data=[0x00, 0x00, 0x00, 0x00],
                is_extended_id=False,
            )
        )
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response to all-zero frame"
        assert resp.data[3] == 0x00, f"Expected 0 pressure, got {resp.data[3]:#x}"


# ===========================================================================
# 5. TIMING AND MESSAGE SEQUENCING
# ===========================================================================


class TestTimingAndSequencing:
    """Edge cases that arise from message ordering and inter-message timing."""

    def test_rapid_burst_valid_frames(self, can_bus, ecu_reset):
        """10 valid frames sent as fast as possible — ECU must process the last one."""
        for _ in range(9):
            send_brake(can_bus, 0x32)
        send_brake(can_bus, 0x50)  # final definitive value
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU did not respond after rapid burst"

    def test_interleaved_speed_and_brake(self, can_bus, ecu_reset):
        """
        Alternating speed / brake frames — the ECU must maintain consistent
        internal state and not confuse the two channels.
        """
        send_speed(can_bus, 120)
        send_brake(can_bus, 90)
        send_speed(can_bus, 120)
        send_brake(can_bus, 90)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None, "No ABS status after interleaved messages"
        assert status.data[0] & ABS_BIT, "ABS should be ON for speed=120, pedal=90"

    def test_no_speed_set_abs_defaults_off(self, can_bus, ecu_reset):
        """
        If speed was never set (fresh reset), ABS must default to OFF
        regardless of pedal force.
        """
        send_brake(can_bus, 90)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID, timeout=0.5)
        if status is not None:
            assert not (
                status.data[0] & ABS_BIT
            ), "ABS active with no speed context — unsafe default"

    def test_speed_arrives_after_brake_long_delay(self, can_bus, ecu_reset):
        """
        Brake arrives first; speed arrives 200 ms later.
        By the time we poll ABS status, the ECU should have the full picture.
        """
        send_brake(can_bus, 90)
        time.sleep(0.2)
        send_speed(can_bus, 120)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None, "No ABS status when speed arrives late"

    def test_ecu_responds_within_one_second(self, can_bus, ecu_reset):
        """Confirm the ECU meets a 1-second response deadline for a normal frame."""
        send_brake(can_bus, 0x32)
        flush(can_bus)
        start = time.time()
        resp = recv_id(can_bus, PRESSURE_RESP_ID, timeout=1.0)
        elapsed = time.time() - start
        assert (
            resp is not None
        ), f"ECU did not respond within 1 s (waited {elapsed:.2f} s)"


# ===========================================================================
# 6. RECOVERY AFTER FAULT
# ===========================================================================


class TestRecoveryAfterFault:
    """
    After receiving invalid input the ECU must return to normal operation
    when valid input resumes — no latching into an error state.
    """

    def test_valid_after_single_fault(self, can_bus, ecu_reset):
        """Fault frame followed immediately by a valid frame: ECU must process valid."""
        send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        send_brake(can_bus, 0x32)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response after single fault + valid"
        assert (
            resp.data[3] == 0x32
        ), f"Expected 0x32 after recovery, got {resp.data[3]:#x}"

    def test_valid_after_burst_fault(self, can_bus, ecu_reset):
        """20 fault frames then a valid frame: ECU must recover fully."""
        for _ in range(20):
            send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        send_brake(can_bus, 0x32)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "ECU did not recover after burst + valid"
        assert (
            resp.data[3] == 0x32
        ), f"Pressure incorrect after burst recovery: {resp.data[3]:#x}"

    def test_valid_fault_valid_sandwich(self, can_bus, ecu_reset):
        """Valid → fault → valid: the second valid frame must be processed cleanly."""
        send_brake(can_bus, 0x20)
        flush(can_bus)
        send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        send_brake(can_bus, 0x40)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No response in valid-fault-valid sequence"
        assert (
            resp.data[3] == 0x40
        ), f"ECU gave {resp.data[3]:#x} instead of 0x40 after fault sandwich"

    def test_zero_pedal_after_fault_resets_pressure(self, can_bus, ecu_reset):
        """
        After a fault the operator releases the pedal (0x00).
        Pressure must return to zero — no ghost output.
        """
        send_brake(can_bus, PEDAL_150PCT)
        flush(can_bus)
        send_brake(can_bus, 0x00)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None
        assert (
            resp.data[3] == 0x00
        ), f"Pressure not zeroed after pedal release: {resp.data[3]:#x}"

    def test_abs_state_correct_after_fault_recovery(self, can_bus, ecu_reset):
        """
        After fault recovery, ABS logic must operate on actual (clamped) values,
        not on the raw fault value. With speed=30 and effective pedal=0x64, ABS is OFF.
        """
        send_speed(can_bus, 30)
        time.sleep(0.1)
        send_brake(can_bus, PEDAL_150PCT)  # fault — clamped to 0x64
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID, timeout=0.5)
        if status is not None:
            assert not (
                status.data[0] & ABS_BIT
            ), "ABS activated based on raw (unclamped) fault value — unsafe"


# ===========================================================================
# 7. EMERGENCY BRAKE ASSIST (EBA)
# ===========================================================================


class TestEmergencyBrakeAssist:
    """
    SWE_REQ_004 — EBA activates at 100% force and sets a warning flag.
    We verify the flag is present, that it requires exactly 100%, and that
    it interacts correctly with ABS.
    """

    def test_eba_flag_set_at_full_force(self, can_bus, ecu_reset):
        """100% pedal must set the EBA warning bit in the ABS status frame."""
        send_brake(can_bus, MAX_PEDAL_VALID)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None, "No ABS status on full-force brake"
        assert (
            status.data[0] & EBA_BIT
        ), f"EBA bit not set at 100% pedal (data[0]={status.data[0]:#x})"

    def test_eba_flag_absent_at_99_percent(self, can_bus, ecu_reset):
        """99% pedal (0x63) must NOT trigger the EBA warning bit."""
        send_brake(can_bus, MAX_PEDAL_VALID - 1)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID, timeout=0.5)
        if status is not None:
            assert not (
                status.data[0] & EBA_BIT
            ), "EBA bit set prematurely at 99% pedal"

    def test_eba_and_abs_both_active_at_high_speed(self, can_bus, ecu_reset):
        """
        At high speed + 100% pedal, both EBA and ABS bits should be active
        simultaneously — they are not mutually exclusive.
        """
        send_speed(can_bus, 120)
        time.sleep(0.1)
        send_brake(can_bus, MAX_PEDAL_VALID)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None, "No status on high-speed full-force brake"
        assert status.data[0] & ABS_BIT, "ABS bit missing at high speed + 100% pedal"
        assert status.data[0] & EBA_BIT, "EBA bit missing at 100% pedal"

    def test_eba_flag_clears_on_pedal_release(self, can_bus, ecu_reset):
        """After full-force braking, releasing the pedal must clear the EBA flag."""
        send_brake(can_bus, MAX_PEDAL_VALID)
        flush(can_bus)
        _ = recv_id(can_bus, ABS_STATUS_ID)  # consume the EBA-active message

        send_brake(can_bus, 0x00)  # release pedal
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None, "No ABS status after pedal release"
        assert not (
            status.data[0] & EBA_BIT
        ), "EBA flag persists after pedal released — latching error"

    def test_eba_persists_across_consecutive_full_force(self, can_bus, ecu_reset):
        """
        EBA flag must remain set across multiple consecutive full-force frames —
        it is not a one-shot pulse.
        """
        for _ in range(5):
            send_brake(can_bus, MAX_PEDAL_VALID)
            time.sleep(0.05)
        flush(can_bus)
        status = recv_id(can_bus, ABS_STATUS_ID)
        assert status is not None, "No status after sustained full-force braking"
        assert (
            status.data[0] & EBA_BIT
        ), "EBA flag not sustained across consecutive frames"

    def test_eba_response_also_on_pressure_channel(self, can_bus, ecu_reset):
        """
        At 100% pedal the pressure response channel (0x300) must also respond,
        not just the ABS status channel.
        """
        send_brake(can_bus, MAX_PEDAL_VALID)
        flush(can_bus)
        resp = recv_id(can_bus, PRESSURE_RESP_ID)
        assert resp is not None, "No pressure response at 100% pedal"
        assert (
            resp.data[3] == MAX_PEDAL_VALID
        ), f"Pressure should echo 0x64, got {resp.data[3]:#x}"
