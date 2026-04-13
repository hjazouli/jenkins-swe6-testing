#include "bcm_cfg.h"
#include "bcm_internal.h"

/**
 * @brief Logic for regen blending.
 * @req SWE_REQ_014
 */
void Bcm_Regen_Calculate(const BcmInput_t* in, BcmOutput_t* out) {
  if (in->motor_torque > 0.0f) {
    float regen_pressure = in->motor_torque / BCM_CFG_REGEN_TORQUE_TO_BAR_RATIO;
    out->hydraulic_pressure -= regen_pressure;

    if (out->hydraulic_pressure < 0.0f) {
      out->hydraulic_pressure = 0.0f;
    }
  }
}
