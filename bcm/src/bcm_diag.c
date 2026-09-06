#include "bcm_internal.h"

/** @brief 2-bit rolling counter for ASW health */
static uint8_t s_heartbeat_cnt = 0;

/**
 * @brief Updates the system heartbeat counter.
 * @req SWE_REQ_015
 */
void BCM_Diag_Update(BcmOutput_t* out) {
  /* Pack heartbeat into bits 6-7 of status_flag (preserving bits 0-5, which
   * hold BCM_FLAG_BRAKE_LIGHT/THERMAL_FAULT/ABS_ACTIVE/HSA_ACTIVE/
   * PLAUS_FAULT/BRAKE_WEAR). Bits 5-7 previously collided with
   * BCM_FLAG_BRAKE_WEAR (bit 5), silently clobbering the wear warning. */
  out->status_flag &= 0x3F;
  out->status_flag |= (uint8_t)(s_heartbeat_cnt << 6);

  /* Increment for next frame (wrap at 4) */
  s_heartbeat_cnt = (uint8_t)((s_heartbeat_cnt + 1) & 0x03);
}

/**
 * @brief Retrieves system health snapshot.
 */
BcmStatus_t BCM_GetDiagStatus(BcmDiagStatus_t* status) {
  if (status == (void*)0) return BCM_STATUS_ERROR;

  status->current_heartbeat = s_heartbeat_cnt;
  /* active_faults logic will expand in Stage 3 */
  status->active_faults = 0x00;

  return BCM_STATUS_OK;
}
