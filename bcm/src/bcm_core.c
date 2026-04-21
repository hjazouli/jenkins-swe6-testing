#include "bcm_iface.h"

#include "bcm_cfg.h"
#include "bcm_internal.h"

/**
 * @brief Initialize the BCM sequencer and outputs.
 */
BcmStatus_t BCM_Init(BcmOutput_t* out) {
  if (out == (void*)0) return BCM_STATUS_ERROR;

  out->hydraulic_pressure = 0.0f;
  out->front_hydraulic_pressure = 0.0f;
  out->rear_hydraulic_pressure = 0.0f;
  out->abs_active = 0;
  out->status_flag = 0x00;

  return BCM_STATUS_OK;
}

/**
 * @brief Orchestrates the BCM execution sequence.
 */
BcmStatus_t BCM_Step(const BcmInput_t* in, BcmOutput_t* out) {
  if ((in == (void*)0) || (out == (void*)0)) return BCM_STATUS_ERROR;

  /* 1. Hardware Monitoring (Stage 3 Entry) */
  if (BCM_HwMon_CheckHardware(in) != BCM_STATUS_OK) {
    /* Potential Fail-safe entry here */
  }

  /* 2. Base mapping & ABS */
  BCM_Abs_ApplyModulation(in, out);

  /* 4. Safety & Distribution */
  BCM_Safety_Check(in, out);
  BCM_Ebd_PerformSplit(in, out);

  /* 5. Assistance Features (End of chain to allow axle overrides) */
  Bcm_Regen_Calculate(in, out);
  BCM_Hsa_RunStateMachine(in, out);

  /* 6. System Health */
  BCM_Diag_Update(out);

  return BCM_STATUS_OK;
}
