import pytest
import time
import re

def parse_telemetry(line):
    """
    Robustly extracts telemetry values using Regex.
    Supports format: [BCM-V101] P:150 S:60 F:100 R:30 Lights:ACTIVE FLAG:0x22
    """
    data = {}
    patterns = {
        'pedal': r'P:(\d+)',
        'speed': r'S:(\d+)',
        'front': r'F:(\d+)',
        'rear': r'R:(\d+)',
        'lights': r'Lights:(\w+)',
        'flag': r'FLAG:(0x[0-9A-Fa-f]+|\d+)'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            val = match.group(1)
            if key == 'flag' and '0x' in val:
                data[key] = int(val, 16)
            elif key == 'lights':
                data[key] = val
            else:
                data[key] = int(val)
    return data

def test_safety_critical_brake_light(bcm_target):
    """REQ_001: The Brake Light MUST turn on when the pedal is pressed."""
    bcm_target.set_pedal(0.0)
    time.sleep(0.1)

    print("\n[ACTION] Testing Brake Light activation...")
    bcm_target.set_pedal(150)
    time.sleep(0.5)

    response = bcm_target.get_status()
    data = parse_telemetry(response)

    assert data.get('lights') == "ACTIVE", "Brake Lights failed to activate!"
    assert data.get('pedal', 0) >= 150, f"Expected Pedal >= 150, got {data.get('pedal')}"

def test_thermal_safety_threshold(bcm_target):
    """REQ_007: Overheating MUST trip a fault flag at 200C."""
    bcm_target.set_temp(45.0)
    time.sleep(0.2)

    print("\n[ACTION] Testing Thermal Fault Threshold (200.5C)...")
    bcm_target.set_temp(200.5)
    time.sleep(0.5)

    response = bcm_target.get_status()
    data = parse_telemetry(response)
    flag_val = data.get('flag', 0)

    # Bit 1 (0x02) is the thermal fault bit in our BCM logic
    assert (flag_val & 0x02) != 0, f"Expected Thermal Fault bit (0x02) in FLAG: {hex(flag_val)}"

def test_speed_plausibility(bcm_target):
    """REQ_011: Fault if speed is high while braking."""
    print("\n[ACTION] Testing Speed/Brake Plausibility...")
    bcm_target.set_speed(120)
    bcm_target.set_pedal(100)
    time.sleep(0.5)

    response = bcm_target.get_status()
    data = parse_telemetry(response)
    flag_val = data.get('flag', 0)

    assert flag_val > 0, "Bcm Safety Monitor failed to detect speed/brake conflict!"

def test_ebd_split(bcm_target):
    """REQ_013: Rear pressure MUST be reduced during high deceleration."""
    print("\n[ACTION] Testing EBD Pressure Split (120 -> 80 km/h)...")
    bcm_target.set_speed(120)
    time.sleep(0.2)
    bcm_target.set_speed(80)
    bcm_target.set_pedal(100)
    time.sleep(0.5)

    response = bcm_target.get_status()
    data = parse_telemetry(response)
    
    f_pres = data.get('front', 0)
    r_pres = data.get('rear', 0)

    assert f_pres > 0, "No hydraulic pressure detected!"
    assert r_pres < f_pres, f"EBD Split failure: Rear ({r_pres}) >= Front ({f_pres})"
    print(f"[REPLY] Verified EBD Split. F: {f_pres}, R: {r_pres}")
