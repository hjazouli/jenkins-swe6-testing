#include "bcm_cfg.h"
#include "bcm_internal.h"

/** @brief History of speed to calculate deceleration */
static float s_ebd_last_speed = 0.0f;

/**
 * @brief Splits pressure between front and rear based on deceleration.
 * @req SWE_REQ_013
 */
void BCM_Ebd_PerformSplit(const BcmInput_t* in, BcmOutput_t* out) {
  /* Calculate deceleration in m/s^2 (Task rate = 10ms = 0.01) */
  float deceleration = ((s_ebd_last_speed - in->vehicle_speed) / 0.01f) / 3.6f;

  if (deceleration > BCM_CFG_EBD_DECEL_THRESHOLD) {
    out->front_hydraulic_pressure = out->hydraulic_pressure;
    out->rear_hydraulic_pressure =
        out->front_hydraulic_pressure * BCM_CFG_EBD_REAR_PRESSURE_RATIO;
  } else {
    out->front_hydraulic_pressure = out->hydraulic_pressure;
    out->rear_hydraulic_pressure = out->front_hydraulic_pressure;
  }

  /* Memory update for next frame */
  s_ebd_last_speed = in->vehicle_speed;
}
