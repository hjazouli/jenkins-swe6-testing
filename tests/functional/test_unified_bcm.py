import pytest
import time
import re
import allure
from tests.bridge.hardware_bridge import Log


@allure.feature("Brake Control Module")
@allure.story("Hydraulic Pressure Map")
def test_safety_critical_brake_light(bcm_target):
    """REQ_001: The Brake Light MUST turn on when the pedal is pressed."""
    Log.test_start("test_safety_critical_brake_light", "Verify brake light activation")

    with allure.step("Initialize system state"):
        bcm_target.set_pedal(0.0)
        time.sleep(0.1)

    with allure.step("Apply high pedal force (150%)"):
        bcm_target.set_pedal(150)
        time.sleep(0.5)

    with allure.step("Verify Clamped Pressure & Light Status"):
        response = bcm_target.get_status()
        data = parse_telemetry(response)

        assert data.get("lights") == "ACTIVE", "Brake Lights failed to activate!"
        assert (
            data.get("pedal", 0) == 100
        ), f"ECU failed to clamp pedal input. Got {data.get('pedal')}"

    Log.test_end("test_safety_critical_brake_light")


@allure.feature("Safety Systems")
@allure.story("Thermal Management")
def test_thermal_safety_threshold(bcm_target):
    """REQ_007: Overheating MUST trip a fault flag at 200C."""
    Log.test_start("test_thermal_safety_threshold", "Verify thermal fault bit at 200C")

    with allure.step("Set normal operating temperature"):
        bcm_target.set_temp(45.0)
        time.sleep(0.2)

    with allure.step("Trigger Overheat condition (200.5C)"):
        bcm_target.set_temp(200.5)
        time.sleep(0.5)

    with allure.step("Check Status Bit 0x02"):
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        flag_val = data.get("flag", 0)
        assert (flag_val & 0x02) != 0, f"Expected Thermal Fault bit (0x02)"

    Log.test_end("test_thermal_safety_threshold")


@allure.feature("Safety Systems")
@allure.story("Plausibility Monitor")
def test_speed_plausibility(bcm_target):
    """REQ_011: Fault if speed is high while braking."""
    Log.test_start("test_speed_plausibility", "Verify speed/brake conflict detection")

    with allure.step("Simulate high-speed hard braking"):
        bcm_target.set_speed(120)
        bcm_target.set_pedal(100)
        time.sleep(0.5)

    with allure.step("Verify Plausibility Fault Bit (0x10)"):
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        flag_val = data.get("flag", 0)
        assert (flag_val & 0x10) != 0, f"Conflict not detected. FLAG: {hex(flag_val)}"

    Log.test_end("test_speed_plausibility")


@allure.feature("Hydraulic Distribution")
@allure.story("Electronic Brake Distribution")
def test_ebd_split(bcm_target):
    """REQ_013: Rear pressure MUST be reduced during high deceleration."""
    Log.test_start("test_ebd_split", "Verify EBD pressure split during deceleration")

    with allure.step("Establish high-speed state"):
        bcm_target.set_speed(120)
        time.sleep(0.2)

    with allure.step("Simulate 80km/h deceleration incident"):
        bcm_target.set_speed(80)
        bcm_target.set_pedal(100)
        time.sleep(0.5)

    with allure.step("Confirm Rear/Front pressure ratio"):
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        f_pres = data.get("front", 0)
        r_pres = data.get("rear", 0)
        assert (
            r_pres < f_pres
        ), f"EBD Split failure: Rear ({r_pres}) >= Front ({f_pres})"

    Log.test_end("test_ebd_split")


def parse_telemetry(line):
    """Helper to extract telemetry from [BCM] stream."""
    data = {}
    patterns = {
        "pedal": r"P:(\d+)",
        "speed": r"S:(\d+)",
        "wear": r"W:(\d+)",
        "front": r"F:(\d+)",
        "rear": r"R:(\d+)",
        "lights": r"Lights:(\w+)",
        "flag": r"FLAG:(0x[0-9A-Fa-f]+|\d+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            val = match.group(1)
            if key == "flag":
                data[key] = int(val, 16) if "0x" in val else int(val)
            elif key == "lights":
                data[key] = val
            else:
                data[key] = int(val)
    return data
