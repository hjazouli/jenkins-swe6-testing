#include "bcm/bcm_cfg.h"
#include "bcm_internal.h"

/* State memory for safety features */
static float s_plaus_last_speed = 0.0f;
static uint8_t s_plaus_counter = 0;
static uint8_t s_plaus_latch = 0x00;

static uint8_t s_thermal_fault_latch = 0x00;
static uint8_t s_thermal_recovery_cnt = 0;

/**
 * @brief Combined safety monitoring for thermal and plausibility.
 * @req SWE_REQ_007, SWE_REQ_008, SWE_REQ_011, SSR_SAF_002
 */
void BCM_Safety_Check(const BcmInput_t* in, BcmOutput_t* out) {
  /* 1. Thermal Latching (SWE_REQ_007) */
  if (in->brake_temp_celsius > BCM_CFG_BRAKE_OVERHEAT_THRESHOLD_C) {
    s_thermal_fault_latch = 0x02;
    s_thermal_recovery_cnt = 0;
  } else if (s_thermal_fault_latch) {
    if (++s_thermal_recovery_cnt >= 3) {
      s_thermal_fault_latch = 0x00;
    }
  }

  /* 2. Safety Clamp (SWE_REQ_008) */
  if (s_thermal_fault_latch &&
      out->hydraulic_pressure > BCM_CFG_THERMAL_CLAMP_MAX_PRESSURE) {
    out->hydraulic_pressure = BCM_CFG_THERMAL_CLAMP_MAX_PRESSURE;
  }

  /* 3. Plausibility Check (SWE_REQ_011) */
  if (in->vehicle_speed >= s_plaus_last_speed && in->pedal_force > 50.0f) {
    if (++s_plaus_counter >= 5) s_plaus_latch = 0x10;
  } else {
    s_plaus_counter = 0;
    s_plaus_latch = 0x00;
  }
  s_plaus_last_speed = in->vehicle_speed;

  /* Apply results to status flag */
  out->status_flag |= (s_thermal_fault_latch | s_plaus_latch);

  /* 4. Signal Quality Check (SSR_SAF_002) - HIGHEST PRIORITY */
  if (in->pedal_sensor_volt < BCM_CFG_PEDAL_VOLT_MIN ||
      in->pedal_sensor_volt > BCM_CFG_PEDAL_VOLT_MAX) {
    /* Set Bit 6 (Fail-Safe) */
    out->status_flag |= BCM_CFG_STATUS_BIT_FAILSAFE;

    /* FORCE 0 Bar - This overrides all previous logic */
    out->hydraulic_pressure = 0.0f;
    out->front_hydraulic_pressure = 0.0f;
    out->rear_hydraulic_pressure = 0.0f;
  }
}

/**
 * @brief Resets internal module state (for testing).
 */
void BCM_Safety_Reset(void) {
  s_plaus_last_speed = 0.0f;
  s_plaus_counter = 0;
  s_plaus_latch = 0x00;
  s_thermal_fault_latch = 0x00;
  s_thermal_recovery_cnt = 0;
}

/**
 * @brief Checks the electrical signal quality of the pedal sensor.
 * @req SSR_SAF_002
 */
void BCM_Safety_Check_Signal_Quality(const BcmInput_t* in, BcmOutput_t* out) {
  if (in->pedal_sensor_volt < BCM_CFG_PEDAL_VOLT_MIN ||
      in->pedal_sensor_volt > BCM_CFG_PEDAL_VOLT_MAX) {
    out->status_flag |= BCM_CFG_STATUS_BIT_FAILSAFE;
    out->hydraulic_pressure = 0.0f;
    out->front_hydraulic_pressure = 0.0f;
    out->rear_hydraulic_pressure = 0.0f;
  }
}