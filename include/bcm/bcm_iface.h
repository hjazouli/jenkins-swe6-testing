#ifndef BCM_IFACE_H
#define BCM_IFACE_H

#include "bcm/bcm_types.h"

/**
 * @brief Initialize the Brake Control Module internal state.
 * @param out Pointer to the output structure to reset.
 * @return BCM_STATUS_OK on success.
 * @req SWE_REQ_001
 */
BcmStatus_t BCM_Init(BcmOutput_t* out);

/**
 * @brief Main periodic task execution for BCM.
 * @param in Pointer to verified input structure.
 * @param out Pointer to output command structure.
 * @return BCM_STATUS_OK if logic executed successfully.
 */
BcmStatus_t BCM_Step(const BcmInput_t* in, BcmOutput_t* out);

/**
 * @brief Retrieve current diagnostic and system health status.
 * @param status Pointer to diagnostic status structure to fill.
 * @return BCM_STATUS_OK on success.
 */
BcmStatus_t BCM_GetDiagStatus(BcmDiagStatus_t* status);

#endif /* BCM_IFACE_H */
