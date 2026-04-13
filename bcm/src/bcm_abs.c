#include "bcm_cfg.h"
#include "bcm_internal.h"

/** @brief Factor to reduce pressure during ABS event */
#define ABS_REDUCTION_FACTOR 0.62f

/**
 * @brief Base hydraulic mapping and ABS modulation.
 * @req SWE_REQ_002, SWE_REQ_004
 */
void BCM_Abs_ApplyModulation(const BcmInput_t* in, BcmOutput_t* out) {
  float validated_pedal = in->pedal_force;

  /* Input Clamping (SWE_REQ_003) */
  if (validated_pedal > 100.0f)
    validated_pedal = 100.0f;
  else if (validated_pedal < 0.0f)
    validated_pedal = 0.0f;

  /* ABS Logic (SWE_REQ_002) */
  if (in->vehicle_speed > 100.0f && validated_pedal > 80.0f) {
    out->hydraulic_pressure = validated_pedal * ABS_REDUCTION_FACTOR;
    out->abs_active = 1;
  } else {
    out->abs_active = 0;
    out->hydraulic_pressure = validated_pedal;
  }
}
