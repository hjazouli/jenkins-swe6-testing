#ifndef BRAKE_LOGIC_H
#define BRAKE_LOGIC_H

#include <stdint.h>

/**
 * Application Software (ASW) Data Structures
 */
typedef struct {
    float pedal_force;      /* 0.0 - 100.0% */
    float vehicle_speed;    /* km/h */
    float wheel_speed;      /* km/h */
    float sensor_wear_volt; /* 0.0 - 5.0V (e.g., 4.5V = 90% wear) */
} BrakeInput_t;

typedef struct {
    float hydraulic_pressure; /* Bar */
    uint8_t abs_active;       /* 0: Inactive, 1: Active */
    uint8_t status_flag;      /* Bit 0: Wear Warning, Bit 1: Overheat */
} BrakeOutput_t;

/**
 * SWE_REQ_003 & 004 & 006: Core logic executed periodically
 */
void Brake_Control_Step(const BrakeInput_t* input, BrakeOutput_t* output);

#endif /* BRAKE_LOGIC_H */
