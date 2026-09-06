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
    
    
@allure.feature("Assistance Systems")
@allure.story("Hill Start Assist")
def test_hsa_hill_start_assist(bcm_target):
    """REQ_009: HSA MUST hold pressure when releasing brake on a hill."""
    Log.test_start("test_hsa_hill_start_assist", "Verify HSA arming and holding")

    with allure.step("1. Arm HSA: Stop car and press brake hard (>80%)"):
        bcm_target.set_speed(0)
        bcm_target.set_pedal(90)
        time.sleep(0.5)
        
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        # Should NOT be active yet (it's only ARMED)
        assert not (data.get("flag", 0) & 0x08), "HSA active too early!"

    with allure.step("2. Trigger HSA: Release pedal (<5%)"):
        bcm_target.set_pedal(0)
        time.sleep(0.5) # Wait for state transition and telemetry
        
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        assert (data.get("flag", 0) & 0x08), "HSA failed to activate on release!"
        assert data.get("front", 0) >= 25, f"HSA pressure too low: {data.get('front')}"

    with allure.step("3. Release HSA: Accelerate (>5 km/h)"):
        bcm_target.set_speed(10)
        time.sleep(0.5)
        
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        assert not (data.get("flag", 0) & 0x08), "HSA failed to release on speed!"
        assert data.get("front", 0) < 5, "HSA pressure still present!"

    Log.test_end("test_hsa_hill_start_assist")


@allure.feature("Diagnostics")
@allure.story("Chip Temperature Sensor")
def test_chip_temperature_telemetry(bcm_target):
    """Verify the MCU's internal temperature sensor is streamed in telemetry."""
    Log.test_start("test_chip_temperature_telemetry", "Verify CHIP_C field is present and sane")

    with allure.step("Wait for a telemetry sample"):
        time.sleep(0.5)

    with allure.step("Verify chip temperature is present and plausible"):
        response = bcm_target.get_status()
        data = parse_telemetry(response)
        assert "chip_c" in data, "CHIP_C field missing from telemetry"

        chip_temp_c = int(float(data["chip_c"]))
        # Generous bound: MCU operating range is -40..105C; a board sitting on
        # a desk should be well within this even with self-heating.
        assert 0 <= chip_temp_c <= 100, f"Implausible chip temperature: {chip_temp_c}C"

    Log.test_end("test_chip_temperature_telemetry")


def parse_telemetry(line):
    """Helper to extract telemetry from [BCM] stream. 
       Handles both raw string lines and pre-parsed dictionaries."""
    if isinstance(line, dict):
        # Convert values to expected types if they aren't already
        processed = {}
        for k, v in line.items():
            if k in ["pedal", "speed", "wear", "front", "rear", "f", "p", "s", "w", "r"]:
                processed[k] = int(float(v))
            elif k == "flag":
                processed[k] = int(v)
            else:
                processed[k] = v
        # Alias short names for test compatibility
        if "f" in processed: processed["front"] = processed["f"]
        if "r" in processed: processed["rear"] = processed["r"]
        if "p" in processed: processed["pedal"] = processed["p"]
        if "s" in processed: processed["speed"] = processed["s"]
        if "w" in processed: processed["wear"] = processed["w"]
        return processed

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
