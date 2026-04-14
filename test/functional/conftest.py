import threading
import time
import can
import pytest
import cantools
import os
import logging

# Configuration and Database Loading
DBC_PATH = os.path.join(os.path.dirname(__file__), "..", "bcm_matrix.dbc")
db = cantools.database.load_file(DBC_PATH)

class VirtualECU(threading.Thread):
    """
    Simulated Electronic Control Unit (ECU) for Brake Control Module testing.
    Mirrors internal C-logic behavioral patterns for SiL/HiL validation.
    """
    def __init__(self, bus: can.BusABC):
        super().__init__()
        self.bus = bus
        self.running = True
        self.daemon = True

        # System State
        self.vehicle_speed = 0
        self.last_vehicle_speed = 0
        self.pedal_voltage = 2500
        self.rain_detected = False
        self.heartbeat = 0
        self.brake_temp = 0
        
        # Latches and Counters
        self.overheat_latch = False
        self.thermal_recovery_cnt = 0
        self.plausibility_fault = False
        self.plaus_counter = 0
        
        # Wiping State Machine 
        self.wiping_active = False
        self.wiping_active_cnt = 100
        self.wiping_period_cnt = 600

    def run(self):
        """Simulation loop execution at 10ms intervals."""
        while self.running:
            self._update_logic()
            msg = self.bus.recv(timeout=0.01)
            if msg:
                self.process_message(msg)
            time.sleep(0.01)

    def _update_logic(self):
        """Internal behavioral logic updates (sequencer)."""
        self.heartbeat = (self.heartbeat + 1) % 8

        # Thermal State Recovery (Hysteresis)
        if self.brake_temp > 200:
            self.overheat_latch = True
            self.thermal_recovery_cnt = 0
        elif self.overheat_latch:
            self.thermal_recovery_cnt += 1
            if self.thermal_recovery_cnt >= 3:
                self.overheat_latch = False

        # ADAS Disc Wiping State Machine
        if self.rain_detected and self.vehicle_speed > 50:
            if self.wiping_active_cnt > 0:
                self.wiping_active = True
                self.wiping_active_cnt -= 1
            else:
                self.wiping_active = False
                if self.wiping_period_cnt > 0:
                    self.wiping_period_cnt -= 1
                else:
                    self.wiping_active_cnt = 100
                    self.wiping_period_cnt = 600
        else:
            self.wiping_active = False
            self.wiping_active_cnt = 100
            self.wiping_period_cnt = 600

    def process_message(self, msg: can.Message):
        """Parses incoming CAN frames and updates ECU output states."""
        if msg.arbitration_id == 0x200:
            signals = db.decode_message("BRAKE_CMD", msg.data)
            pedal = signals.get("Pedal_Force", 0)
            self.pedal_voltage = signals.get("Pedal_Voltage", 2500)

            out_pressure = pedal
            status_signals = {
                "FailSafe_Flag": 0,
                "Overheat_Flag": 0,
                "Heartbeat": self.heartbeat,
            }

            # Plausibility Verification
            if self.vehicle_speed >= self.last_vehicle_speed and pedal > 50:
                self.plaus_counter += 1
                if self.plaus_counter >= 5:
                    self.plausibility_fault = True
            else:
                self.plaus_counter = 0
                self.plausibility_fault = False

            # Signal Quality and Fail-Safe Logic
            if self.pedal_voltage < 500 or self.pedal_voltage > 4500:
                out_pressure = 0
                status_signals["FailSafe_Flag"] = 1
            
            if self.plausibility_fault:
                status_signals["FailSafe_Flag"] = 1

            # Thermal Clamping Logic
            if self.overheat_latch:
                status_signals["Overheat_Flag"] = 1
                if out_pressure > 50:
                    out_pressure = 50

            # ABS Modulation
            if self.vehicle_speed > 100 and out_pressure > 80:
                out_pressure = int(out_pressure * 0.62)

            # ADAS Pressure Arbitration
            if self.wiping_active and out_pressure < 2:
                out_pressure = 2

            front_pressure = out_pressure
            rear_pressure = out_pressure

            # EBD Splitting Logic
            decel = ((self.last_vehicle_speed - self.vehicle_speed) / 0.01) / 3.6
            if decel > 5.0:
                rear_pressure = int(front_pressure * 0.70)

            self.last_vehicle_speed = self.vehicle_speed

            # Transmission of Feedback and Status Frames
            feedback_data = db.encode_message(
                "PRESSURE_FB",
                {
                    "Front_Pressure": int(front_pressure),
                    "Rear_Pressure": int(rear_pressure),
                },
            )
            self.bus.send(can.Message(arbitration_id=0x300, data=feedback_data))

            status_data = db.encode_message("STATUS_FB", status_signals)
            self.bus.send(can.Message(arbitration_id=0x400, data=status_data))

        elif msg.arbitration_id == 0x100:
            self._reset_state()

        elif msg.arbitration_id == 0x210:
            signals = db.decode_message("VEH_SPEED", msg.data)
            self.vehicle_speed = signals.get("Vehicle_Speed", 0)
            self.rain_detected = bool(signals.get("Rain_Sensor", 0))

        elif msg.arbitration_id == 0x220:
            signals = db.decode_message("BRAKE_TEMP", msg.data)
            self.brake_temp = signals.get("Brake_Temperature", 0)

    def _reset_state(self):
        """Resets internal state variables to default calibrated values."""
        self.overheat_latch = False
        self.thermal_recovery_cnt = 0
        self.plausibility_fault = False
        self.plaus_counter = 0
        self.brake_temp = 0
        self.vehicle_speed = 0
        self.last_vehicle_speed = 0
        self.rain_detected = False
        self.wiping_active = False

    def stop(self):
        self.running = False

@pytest.fixture(scope="session")
def can_bus():
    """Provides a virtual CAN bus interface for the test session."""
    bus = can.interface.Bus(channel="vbus_train", interface="virtual")
    ecu_bus = can.interface.Bus(channel="vbus_train", interface="virtual")
    ecu = VirtualECU(ecu_bus)
    ecu.start()
    yield bus
    ecu.stop()
    bus.shutdown()
    ecu_bus.shutdown()

@pytest.fixture
def ecu_reset(can_bus):
    """Ensures a clean ECU state before each test case."""
    can_bus.send(can.Message(arbitration_id=0x100, data=[0x00, 0x11]))
    time.sleep(0.1)
