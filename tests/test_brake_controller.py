import pytest
import can
import time

def test_brake_pressure_response(can_bus):
    """
    SWE.6 Test Case: Verify ECU responds to brake pedal signal.
    Polarion: SWE_REQ_001
    """
    # 1. Send Brake Pedal Position (50% = 0x32)
    pedal_pos = 0x32
    brake_signal = can.Message(
        arbitration_id=0x200,
        data=[0x00, 0x00, 0x00, pedal_pos],
        is_extended_id=False
    )
    
    can_bus.send(brake_signal)
    
    # 2. Flush and Receive Pressure Response (Expecting 0x300)
    # Drain any stale messages from the buffer
    while can_bus.recv(timeout=0): pass
    
    response = None
    timeout = time.time() + 1.0
    while time.time() < timeout:
        msg = can_bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == 0x300:
            response = msg
            break
            
    assert response is not None, "ECU did not respond to brake pedal!"
    
    # 3. Verify Data (Data[3] should be 0x32)
    pressure = response.data[3]
    assert pressure == pedal_pos, f"Expected {pedal_pos} bar, got {pressure}"
    
    print(f"✅ PASSED: Brake pressure verification successful.")

@pytest.mark.parametrize("speed,pedal,expected_abs", [
    (120, 90, 1), # High speed + hard brake = ABS ON
    (30, 90, 0),  # Low speed + hard brake = ABS OFF
    (120, 20, 0), # High speed + light brake = ABS OFF
])
def test_abs_activation_logic(can_bus, ecu_reset, speed, pedal, expected_abs):
    """
    SWE.6 Test Case: Verify ABS activation logic based on speed and pedal force.
    Polarion: SWE_REQ_002
    """
    # 1. Set Vehicle Speed
    speed_msg = can.Message(
        arbitration_id=0x210,
        data=[0x00, 0x00, speed],
        is_extended_id=False
    )
    can_bus.send(speed_msg)
    time.sleep(0.1) # Give background thread time to process
    
    # 2. Set Brake Pedal Force
    brake_msg = can.Message(
        arbitration_id=0x200,
        data=[0x00, 0x00, 0x00, pedal],
        is_extended_id=False
    )
    can_bus.send(brake_msg)
    
    # 3. Flush and Receive Status Response (Expecting 0x400)
    # Drain any stale messages from the buffer
    while can_bus.recv(timeout=0): pass
    
    status_msg = None
    timeout = time.time() + 1.0
    while time.time() < timeout:
        msg = can_bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == 0x400:
            status_msg = msg
            break
            
    assert status_msg is not None, "ECU did not send ABS status!"
    
    # 4. Verify ABS bit
    actual_abs = status_msg.data[0] & 0x01
    assert actual_abs == expected_abs, f"Expected ABS {expected_abs}, got {actual_abs} for spd={speed}, pedal={pedal}"
    
    print(f"✅ PASSED: ABS logic verification for Speed={speed}, Pedal={pedal}")
