#include "bcm_cfg.h"
#include "bcm_iface.h"

/* State memory for safety features */
static float s_plaus_last_speed = 0.0f;
static uint8_t s_plaus_counter = 0;
static uint8_t s_plaus_latch = 0x00;

static uint8_t s_thermal_fault_latch = 0x00;
static uint8_t s_thermal_recovery_cnt = 0;

/* Hysteresis constants (should ideally be in bcm_cfg.h) */
#define HYDRAULIC_PRESSURE_HIGH_THRESHOLD 5.0f
#define HYDRAULIC_PRESSURE_LOW_THRESHOLD  2.0f

/**
 * @brief Combined safety monitoring for lights, thermal and plausibility.
 */
void BCM_Safety_Check(const BcmInput_t* in, BcmOutput_t* out) {
  /* 0. Brake Light Control with Hysteresis */
  if (out->hydraulic_pressure > HYDRAULIC_PRESSURE_HIGH_THRESHOLD) {
    out->status_flag |= BCM_FLAG_BRAKE_LIGHT;
  } else if (out->hydraulic_pressure < HYDRAULIC_PRESSURE_LOW_THRESHOLD) {
    out->status_flag &= ~BCM_FLAG_BRAKE_LIGHT;
  }

  /* 1. Thermal Latching (SWE_REQ_007) */
  if (in->brake_temp_celsius > BCM_CFG_BRAKE_OVERHEAT_THRESHOLD_C) {
    s_thermal_fault_latch = BCM_FLAG_THERMAL_FAULT;
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
    if (++s_plaus_counter >= 5) s_plaus_latch = BCM_FLAG_PLAUS_FAULT;
  } else {
    s_plaus_counter = 0;
    s_plaus_latch = 0x00;
  }
  s_plaus_last_speed = in->vehicle_speed;

  /* 4. ABS State Integration */
  uint8_t abs_status = (out->abs_active) ? BCM_FLAG_ABS_ACTIVE : 0x00;

  /* Apply results to status flag */
  out->status_flag |= (s_thermal_fault_latch | s_plaus_latch | abs_status);
}
