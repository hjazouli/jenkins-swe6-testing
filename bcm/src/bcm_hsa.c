#include "bcm_cfg.h"
#include "bcm_internal.h"

/** @brief Counter for the 2.0s hold duration */
static uint16_t s_hsa_timer = 0;

/**
 * @brief State machine for Hill Start Assist logic.
 * @req SWE_REQ_009
 */
void BCM_Hsa_RunStateMachine(const BcmInput_t *in, BcmOutput_t *out) {
  /* 1. Arming condition: Car stopped and brakes applied hard */
  if (in->vehicle_speed == 0.0f && in->pedal_force > 80.0f) {
    s_hsa_timer = BCM_CFG_HSA_HOLD_DURATION_CYCLES;
  }

  /* 2. Holding logic: Activated when driver releases pedal while armed */
  if (s_hsa_timer > 0) {
    if (in->pedal_force < 5.0f) {
      /* Specifically lock REAR brakes to prevent rollback @req SWE_REQ_009 */
      out->rear_hydraulic_pressure = BCM_CFG_HSA_HOLD_PRESSURE;
      out->status_flag |= BCM_FLAG_HSA_ACTIVE;
      s_hsa_timer--;
    }

    /* 3. Abort/Release logic: Car starts moving faster than threshold */
    if (in->vehicle_speed > BCM_CFG_RELEASE_SPEED_THRESHOLD) {
      s_hsa_timer = 0;
    }
  }
}
