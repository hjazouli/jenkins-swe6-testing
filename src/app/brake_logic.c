#include "brake_logic.h"

/* Static state management for persistent data between frames */
static uint8_t brake_warning_flag = 0;

/**
 * Brake_Control_Step: SWE.6 Functional Logic (ASW)
 * This function calculates the target hydraulic pressure based on user input,
 * vehicle speed, and wheel slip to prevent wheel lockup (ABS).
 */
void Brake_Control_Step(const BrakeInput_t* input, BrakeOutput_t* output) {
    // 1. Input Clamping (SWE_REQ_003: Safety rejection of out-of-bounds inputs)
    float validated_pedal = input->pedal_force;
    if (validated_pedal > 100.0f) {
        validated_pedal = 100.0f;
    } else if (validated_pedal < 0.0f) {
        validated_pedal = 0.0f;
    }

    // 2. ABS Logic (Slip-based intervention)
    // Slip = (VehicleSpeed - WheelSpeed) / VehicleSpeed
    float slip = 0.0f;
    if (input->vehicle_speed > 1.0f) {
        slip = (input->vehicle_speed - input->wheel_speed) / input->vehicle_speed;
    }

    // High speed (>5 km/h) and high slip (>15%) triggers ABS
    if (slip > 0.15f && input->vehicle_speed > 5.0f) {
        // ABS Intervention: Reduce target pressure to avoid total lock
        output->hydraulic_pressure = validated_pedal * 0.62f; 
        output->abs_active = 1;
    } else {
        // Normal braking
        output->hydraulic_pressure = validated_pedal;
        output->abs_active = 0;
    }

    // 3. Wear Monitoring (SWE_REQ_006)
    // Assume 4.5V threshold = 90% wear on the sensor (Standard 5V ADC)
    if (input->sensor_wear_volt > 4.5f) {
        brake_warning_flag |= 0x01; // Set Bit 0 for Wear Warning
    }
    
    output->status_flag = brake_warning_flag;
}
