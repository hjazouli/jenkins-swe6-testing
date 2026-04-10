#ifndef BRAKE_LOGIC_H
#define BRAKE_LOGIC_H

#include <stdint.h>

/* SWE_REQ_002: ABS pressure reduction factor during wheel slip intervention */
#define ABS_PRESSURE_REDUCTION_FACTOR 0.62f

/* SWE_REQ_005: Overheat threshold in degrees Celsius */
#define BRAKE_OVERHEAT_THRESHOLD_C 200.0f

/* SWE_REQ_006: Wear sensor voltage threshold (90% wear on a 5V ADC) */
#define BRAKE_WEAR_VOLTAGE_THRESHOLD 4.5f

/**
 * Application Software (ASW) Data Structures
 */
typedef struct {
  float pedal_force;        /* 0.0 - 100.0% */
  float vehicle_speed;      /* km/h */
  float wheel_speed;        /* km/h */
  float sensor_wear_volt;   /* 0.0 - 5.0V (e.g., 4.5V = 90% wear) */
  float brake_temp_celsius; /* SWE_REQ_005: Brake temperature in °C */
} BrakeInput_t;

typedef struct {
  float hydraulic_pressure; /* Bar */
  uint8_t abs_active;       /* 0: Inactive, 1: Active */
  uint8_t status_flag;      /* Bit 0: ABS Active, Bit 1: Overheat, Bit 3 (0x08):
                               Wear Warning */
} BrakeOutput_t;

/**
 * SWE.6 Unit Interfaces
 */
void Brake_Control_Init(BrakeOutput_t* output);
void Brake_Control_Step(const BrakeInput_t* input, BrakeOutput_t* output);

#endif /* BRAKE_LOGIC_H */
