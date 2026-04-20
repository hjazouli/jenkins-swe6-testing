import ctypes
import os

class SimBridge:
    def __init__(self, bcm_dll):
        self.bcm = bcm_dll
        # Note: In a real SiL, we'd load the .so/.dll here if not passed
        if self.bcm:
            self.input_struct = self.bcm.BcmInput_t()
            self.output_struct = self.bcm.BcmOutput_t()
        else:
            self.input_struct = None
            self.output_struct = None

    def set_pedal(self, force: float):
        if self.input_struct: self.input_struct.pedal_force = force
        self._step()

    def set_temp(self, temp: float):
        if self.input_struct: self.input_struct.brake_temp_celsius = temp
        self._step()

    def set_speed(self, speed: float):
        if self.input_struct: self.input_struct.vehicle_speed = speed
        self._step()

    def _step(self):
        if self.bcm:
            self.bcm.BCM_Safety_Check(ctypes.byref(self.input_struct), ctypes.byref(self.output_struct))
            self.bcm.BCM_Ebd_PerformSplit(ctypes.byref(self.input_struct), ctypes.byref(self.output_struct))

    def get_status(self) -> str:
        if not self.input_struct: return "[SIM] Error: DLL Not Loaded"
        pedal_str = "DEPRESSED" if self.input_struct.pedal_force > 0.1 else "IDLE"
        brake_str = "ACTIVE" if (self.output_struct.status_flag & 0x01) else "INACTIVE"
        if self.input_struct.pedal_force > 0.1:
            return f"[BCM] Pedal: {pedal_str} | Lights: {brake_str} | F: {int(self.output_struct.front_hydraulic_pressure)} | R: {int(self.output_struct.rear_hydraulic_pressure)}"
        return f"[BCM] Status: IDLE | FLAG: {self.output_struct.status_flag}"

    def close(self):
        pass
