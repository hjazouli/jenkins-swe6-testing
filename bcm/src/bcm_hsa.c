#include "bcm_cfg.h"
#include "bcm_internal.h"

/** @brief Counter for the 2.0s hold duration */
static uint16_t s_hsa_timer = 0;

typedef enum {
  HSA_STATE_IDLE = 0,
  HSA_STATE_ARMED,
  HSA_STATE_HOLDING
} HsaState_t;

static HsaState_t s_hsa_state = HSA_STATE_IDLE;

/**
 * @brief Initialize HSA internal state.
 */
void BCM_Hsa_Init(void) {
  s_hsa_state = HSA_STATE_IDLE;
  s_hsa_timer = 0;
}

/**
 * @brief State machine for Hill Start Assist logic.
 * @req SWE_REQ_009
 */
void BCM_Hsa_RunStateMachine(const BcmInput_t *in, BcmOutput_t *out) {
  if (in == (void *)0 || out == (void *)0) return;

  switch (s_hsa_state) {
    case HSA_STATE_IDLE:
      /* Ensure flag is cleared in IDLE */
      out->status_flag &= ~BCM_FLAG_HSA_ACTIVE;
      /* Arming condition: Car is stopped and driver presses brake hard (>80%) */
      if ((in->vehicle_speed < 0.1f) && (in->pedal_force > 80.0f)) {
        s_hsa_state = HSA_STATE_ARMED;
      }
      break;

    case HSA_STATE_ARMED:
      /* Ensure flag is cleared in ARMED */
      out->status_flag &= ~BCM_FLAG_HSA_ACTIVE;
      /* Transition to holding if driver releases the pedal (<5%) */
      if (in->pedal_force < 5.0f) {
        s_hsa_state = HSA_STATE_HOLDING;
        s_hsa_timer = BCM_CFG_HSA_HOLD_DURATION_CYCLES;
      }
      /* Abort if car starts moving or pedal is re-released? No, just if car moves
       */
      if (in->vehicle_speed > BCM_CFG_RELEASE_SPEED_THRESHOLD) {
        s_hsa_state = HSA_STATE_IDLE;
      }
      break;

    case HSA_STATE_HOLDING:
      /* Set the active flag and apply hold pressure */
      out->status_flag |= BCM_FLAG_HSA_ACTIVE;
      out->front_hydraulic_pressure = BCM_CFG_HSA_HOLD_PRESSURE;
      out->rear_hydraulic_pressure = BCM_CFG_HSA_HOLD_PRESSURE;

      if (s_hsa_timer > 0) {
        s_hsa_timer--;
      }

      /* Release conditions:
       * 1. Timer expired
       * 2. Vehicle speed exceeds threshold
       * 3. Driver re-applies brake (manual takeover)
       */
      if ((s_hsa_timer == 0) ||
          (in->vehicle_speed > BCM_CFG_RELEASE_SPEED_THRESHOLD) ||
          (in->pedal_force > 10.0f)) {
        s_hsa_state = HSA_STATE_IDLE;
      }
      break;

    default:
      s_hsa_state = HSA_STATE_IDLE;
      break;
  }
}
