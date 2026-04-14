#ifndef BCM_TYPES_H
#define BCM_TYPES_H

#include <stdint.h>
#include <stdbool.h>

/**
 * @brief Standard return codes for BCM functions.
 */
typedef enum {
  BCM_STATUS_OK = 0,
  BCM_STATUS_ERROR,
  BCM_STATUS_NOT_IMPL
} BcmStatus_t;

/**
 * @brief BCM Input data from the BSW/Sensors layer.
 */
typedef struct {
  /** @brief Driver pedal force [0.0 - 100.0 %] */
  float pedal_force;
  /** @brief Raw pedal sensor voltage [0.0 - 5.0 V] */
  float pedal_sensor_volt;
  /** @brief Vehicle speed from wheel sensors [km/h] */
  float vehicle_speed;
  /** @brief Current brake temperature [Celsius] */
  float brake_temp_celsius;
  /** @brief Regenerative torque available from motor [Nm] */
  float motor_torque;
  /** @brief Flag indicating rain presence (from rain sensor) */
  bool rain_detected;
} BcmInput_t;

/**
 * @brief BCM Output data to the Hydraulic/CAN layer.
 */
typedef struct {
  /** @brief Target master hydraulic pressure [Bar] */
  float hydraulic_pressure;
  /** @brief Target pressure for front axle [Bar] @req SWE_REQ_013 */
  float front_hydraulic_pressure;
  /** @brief Target pressure for rear axle [Bar] @req SWE_REQ_013 */
  float rear_hydraulic_pressure;
  /** @brief ABS active status [0: Inactive, 1: Active] */
  uint8_t abs_active;
  /** @brief Status flags for diag/HMI [Bitmask] */
  uint8_t status_flag;
} BcmOutput_t;

/**
 * @brief Diagnostic Status structure for external monitoring.
 */
typedef struct {
  uint8_t current_heartbeat;
  uint8_t active_faults;
} BcmDiagStatus_t;

/* Backward Compatibility Aliases */
typedef BcmInput_t BrakeInput_t;
typedef BcmOutput_t BrakeOutput_t;

#endif /* BCM_TYPES_H */
