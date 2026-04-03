import pytest
import can
import time
import threading

# --- Virtual ECU Simulator ---
# This class runs in a background thread and acts as the "Hardware" (TC397 ECU)
class VirtualECU(threading.Thread):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.running = True
        self.daemon = True
        self.vehicle_speed = 0

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

    def process_message(self, msg):
        # 0x210: Vehicle Speed
        if msg.arbitration_id == 0x210:
            self.vehicle_speed = msg.data[2]
            print(f"[Virtual ECU] Updated VehSpeed: {self.vehicle_speed} km/h")

        # 0x100: ECU Reset
        elif msg.arbitration_id == 0x100:
            print("[Virtual ECU] Resetting state...")
            self.vehicle_speed = 0

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
                is_extended_id=False
            )
            self.bus.send(response)

            # Simulate ABS Status logic
            # If speed > 100 AND brake > 80% -> Activate ABS (Bit 0 of status)
            abs_active = 0x01 if (self.vehicle_speed > 100 and pedal_value > 80) else 0x00
            status_msg = can.Message(
                arbitration_id=0x400, # Status ID
                data=[abs_active, 0x00],
                is_extended_id=False
            )
            self.bus.send(status_msg)

    def stop(self):
        self.running = False

@pytest.fixture(scope="session")
def can_bus():
    """Initialize Virtual CAN interface."""
    # Test bus instance
    bus = can.interface.Bus(
        channel='vbus_shared',
        interface='virtual'
    )
    
    # Separate bus instance for the ECU
    ecu_bus = can.interface.Bus(
        channel='vbus_shared',
        interface='virtual'
    )
    
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
        arbitration_id=0x100,
        data=[0x02, 0x11, 0x01],
        is_extended_id=False
    )
    can_bus.send(reset_msg)
    time.sleep(0.1) # Simulate boot time
