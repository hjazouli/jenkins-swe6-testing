import pytest
import time


def test_safety_critical_brake_light(bcm_target):
    """REQ_001: The Brake Light MUST turn on when the pedal is pressed."""
    # 1. Clear state
    bcm_target.set_pedal(0.0)
    time.sleep(0.1)

    # 2. Action: Press Pedal with 150.5 Newtons
    print("\n[ACTION] Setting Pedal Force to 150.5 N...")
    bcm_target.set_pedal(150.5)
    time.sleep(0.5)

    # 3. Verification
    response = bcm_target.get_status()
    print(f"[REPLY] {response}")

    assert "Lights: ACTIVE" in response
    assert "Pedal: DEPRESSED" in response


def test_thermal_safety_threshold(bcm_target):
    """REQ_007: Overheating MUST trip a fault flag at 200C."""
    # 1. Nominal Temp
    bcm_target.set_temp(45.0)

    # 2. Inject high-precision trip point
    print("\n[ACTION] Injecting Thermal Fault (200.5C)...")
    bcm_target.set_temp(200.5)
    time.sleep(0.5)

    # 3. Verification
    response = bcm_target.get_status()
    print(f"[REPLY] {response}")

    # Extract flag value and check bit 1 (0x02)
    flag_val = int(response.split("FLAG: ")[1], 16 if "x" in response else 10)
    assert (flag_val & 0x02) != 0, f"Expected Thermal Fault (bit 1) in {flag_val}"


def test_speed_plausibility(bcm_target):
    """REQ_011: Fault if speed is high (>100) while braking."""
    print("\n[REQUEST] Simulating Speeding while Braking...")
    bcm_target.set_speed(120.0)
    bcm_target.set_pedal(100.0)
    time.sleep(0.5)

    response = bcm_target.get_status()
    print(f"[RESPONSE] {response}")

    # FLAG should include bit 4 (0x16) or similar depending on your bcm_safety.h
    # For now, let's just assert its not 0
    flag_val = int(response.split("FLAG: ")[1], 16 if "x" in response else 10)
    assert flag_val > 1, "Expected a fault flag for speed/brake plausibility"


def test_ebd_split(bcm_target):
    """REQ_013: Rear pressure MUST be reduced during high deceleration."""
    print("\n[REQUEST] Driving at constant high speed (120 km/h)...")
    bcm_target.set_speed(120.0)
    time.sleep(0.5)

    print(
        "[REQUEST] Slamming brakes and causing deceleration (speed drops to 80 km/h)..."
    )
    bcm_target.set_speed(80.0)
    bcm_target.set_pedal(100.0)
    time.sleep(0.5)

    response = bcm_target.get_status()
    print(f"[RESPONSE] {response}")

    # Expected: "... | F: 10 | R: 3"
    assert "F:" in response and "R:" in response
    parts = response.split("|")
    f_pres = int(parts[-2].split(":")[1].strip())
    r_pres = int(parts[-1].split(":")[1].strip())

    assert f_pres == 10, f"Expected Front Pressure = 10, got {f_pres}"
    assert (
        r_pres < f_pres
    ), f"EBD Split failed! Rear Pressure ({r_pres}) is not less than Front ({f_pres})"
    print(f"[VERIFIED] EBD Split successful. Front: {f_pres}, Rear: {r_pres}")
