#include "brake_logic.h"

/* Static state management for persistent data between frames */
static uint8_t brake_warning_flag = 0;

/**
 * Brake_Control_Step: SWE.6 Functional Logic (ASW)
 * This function calculates the target hydraulic pressure based on user input,
 * vehicle speed, and wheel slip to prevent wheel lockup (ABS).
 *
 * Requirements covered: SWE_REQ_002, SWE_REQ_003, SWE_REQ_005, SWE_REQ_006
 */
void Brake_Control_Step(const BrakeInput_t* input, BrakeOutput_t* output) {
    /* ---------------------------------------------------------------
     * 1. Input Clamping (SWE_REQ_003: Safety rejection of OOB inputs)
     * --------------------------------------------------------------- */
    float validated_pedal = input->pedal_force;
    if (validated_pedal > 100.0f) {
        validated_pedal = 100.0f;
    } else if (validated_pedal < 0.0f) {
        validated_pedal = 0.0f;
    }

    /* ---------------------------------------------------------------
     * 2. ABS Logic (SWE_REQ_002)
     * Activates when speed > 100 km/h AND pedal force > 80%
     * (high-speed hard-braking scenario → risk of wheel lockup)
     * --------------------------------------------------------------- */
    if (input->vehicle_speed > 100.0f && validated_pedal > 80.0f) {
        /* ABS Intervention: Reduce target pressure to avoid total lock */
        output->hydraulic_pressure = validated_pedal * ABS_PRESSURE_REDUCTION_FACTOR;
        output->abs_active = 1;
    } else {
        /* Normal braking */
        output->hydraulic_pressure = validated_pedal;
        output->abs_active = 0;
    }

    /* ---------------------------------------------------------------
     * 3. Re-evaluate warning flags fresh each cycle (no permanent latch)
     *    This allows flags to self-clear once the fault condition resolves.
     * --------------------------------------------------------------- */
    brake_warning_flag = 0x00;

    /* SWE_REQ_006: Wear Monitoring
     * Bit 3 (0x08): sensor_wear_volt > BRAKE_WEAR_VOLTAGE_THRESHOLD → 90% worn */
    if (input->sensor_wear_volt > BRAKE_WEAR_VOLTAGE_THRESHOLD) {
        brake_warning_flag |= 0x08;
    }

    /* SWE_REQ_005: Overheat Monitoring
     * Bit 1 (0x02): brake_temp_celsius > BRAKE_OVERHEAT_THRESHOLD_C → Overheat */
    if (input->brake_temp_celsius > BRAKE_OVERHEAT_THRESHOLD_C) {
        brake_warning_flag |= 0x02;
    }

    /* Bit 0 (0x01): Mirror ABS active state into the status flag */
    if (output->abs_active) {
        brake_warning_flag |= 0x01;
    }

    output->status_flag = brake_warning_flag;
}
