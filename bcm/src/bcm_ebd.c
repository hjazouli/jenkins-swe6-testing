#include "bcm_cfg.h"
#include "bcm_internal.h"

/** @brief History of speed to calculate deceleration */
static float s_ebd_last_speed = 0.0f;
static int s_ebd_latch_timer = 0;

void BCM_Ebd_PerformSplit(const BcmInput_t* in, BcmOutput_t* out) {
  /* Calculate deceleration in m/s^2 (Task rate = 10ms = 0.01s) */
  float deceleration = ((s_ebd_last_speed - in->vehicle_speed) / 0.01f) / 3.6f;

  /* EBD Activation with 2000ms (200 ticks) Latch */
  if (deceleration > BCM_CFG_EBD_DECEL_THRESHOLD) {
    s_ebd_latch_timer = 200; 
  }

  if (s_ebd_latch_timer > 0) {
    out->front_hydraulic_pressure = out->hydraulic_pressure;
    out->rear_hydraulic_pressure =
        out->front_hydraulic_pressure * BCM_CFG_EBD_REAR_PRESSURE_RATIO;
    s_ebd_latch_timer--;
  } else {
    out->front_hydraulic_pressure = out->hydraulic_pressure;
    out->rear_hydraulic_pressure = out->front_hydraulic_pressure;
  }

  s_ebd_last_speed = in->vehicle_speed;
}
