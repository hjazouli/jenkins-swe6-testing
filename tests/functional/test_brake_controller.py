import pytest
import time
import allure
from test_unified_bcm import parse_telemetry
from tests.bridge.hardware_bridge import Log

# Corrected bitmask based on bcm_types.h
BRAKE_LIGHT_BIT = 0x01
THERMAL_FAULT_BIT = 0x02
ABS_ACTIVE_BIT = 0x04

@allure.feature("Brake Control Module")
class TestPedalBoundary:
    """Verify the ECU handles every boundary of the pedal range correctly."""

    @allure.story("Pedal Boundary Verification")
    def test_zero_pedal(self, bcm_target):
        """0 input: ECU must respond with zero pressure."""
        Log.test_start("test_zero_pedal", "Verify 0% pedal results in 0 Bar pressure")
        
        with allure.step("Command 0.0% Pedal"):
            bcm_target.set_pedal(0.0)
            time.sleep(0.5)

        with allure.step("Verify Zero Pressure Output"):
            response = bcm_target.get_status()
            data = parse_telemetry(response)
            assert data.get('front', -1) == 0, f"Expected 0 pressure"
        
        Log.test_end("test_zero_pedal")

    @allure.story("Pedal Boundary Verification")
    def test_exact_max(self, bcm_target):
        """100%: maximum valid value — must not be clamped or rejected."""
        Log.test_start("test_exact_max", "Verify 100% pedal is accurately processed")
        
        with allure.step("Command 100.0% Pedal"):
            bcm_target.set_pedal(100.0)
            time.sleep(0.5)

        with allure.step("Verify 100% State"):
            response = bcm_target.get_status()
            data = parse_telemetry(response)
            assert data.get('pedal', 0) == 100, f"Expected 100% pedal"
        
        Log.test_end("test_exact_max")

    @allure.story("Pedal Boundary Verification")
    def test_one_above_max(self, bcm_target):
        """101%: ECU must clamp to 100%."""
        Log.test_start("test_one_above_max", "Verify input clamping at 100% boundary")
        
        with allure.step("Command 101.0% Pedal (Over-range)"):
            bcm_target.set_pedal(101.0)
            time.sleep(0.5)

        with allure.step("Confirm Clamping to 100%"):
            response = bcm_target.get_status()
            data = parse_telemetry(response)
            assert data.get('pedal', 0) <= 100, f"ECU failed to clamp"
        
        Log.test_end("test_one_above_max")

@allure.feature("Safety Systems")
class TestStatusFlags:
    """Verify ABS, Overheat, and Wear flags are set correctly in the status byte."""

    @allure.story("ABS Activation Logic")
    @pytest.mark.parametrize(
        "speed,pedal,expected_abs",
        [
            (120, 90, True),  # high speed + hard brake  → ON
            (30, 90, False),  # low speed  + hard brake  → OFF
            (120, 20, False), # high speed + light brake → OFF
        ],
    )
    def test_abs_logic(self, bcm_target, speed, pedal, expected_abs):
        Log.test_start("test_abs_logic", f"Verify ABS Engagement (Spd:{speed}, Pdl:{pedal})")
        
        with allure.step(f"Set Vehicle Conditions (Spd:{speed}km/h, Pdl:{pedal}%)"):
            bcm_target.set_speed(speed)
            bcm_target.set_pedal(pedal)
            time.sleep(0.5)

        with allure.step(f"Verify ABS Active Bit (0x04) is {'Set' if expected_abs else 'Clear'}"):
            response = bcm_target.get_status()
            data = parse_telemetry(response)
            flag_val = data.get('flag', 0)
            actual = bool(flag_val & ABS_ACTIVE_BIT)
            assert actual == expected_abs, f"Expected ABS={expected_abs}, got FLAG={hex(flag_val)}"
        
        Log.test_end("test_abs_logic")

    def test_brake_overheat_warning(self, bcm_target):
        """Verify Brake Overheat flag is set when temperature > 200°C."""
        Log.test_start("test_brake_overheat_warning", "Verify thermal fault flag triggering > 200C")
        bcm_target.set_temp(250.0)
        bcm_target.set_pedal(50.0)
        time.sleep(0.5)
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        
        # Overheat Bit is 0x02
        flag_val = data.get('flag', 0)
        assert (flag_val & THERMAL_FAULT_BIT), f"Expected Overheat flag, got {hex(flag_val)}"
        Log.test_end("test_brake_overheat_warning")

    def test_brake_wear_warning(self, bcm_target):
        """Verify Brake Wear flag is set when wear > 90%."""
        # Wear isn't directly settable in UART commands based on current firmware.
        # So we skip this or mark as expected-to-fail based on logic.
        pytest.skip("Wear parameter not currently mapped via UART control in firmware.")
