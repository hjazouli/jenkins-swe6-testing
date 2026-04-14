#ifndef BCM_INTERNAL_H
#define BCM_INTERNAL_H

#include "bcm/bcm_types.h"

/* Internal APIs for core sequencer to call sub-modules */

void BCM_Abs_ApplyModulation(const BcmInput_t* in, BcmOutput_t* out);
void Bcm_Regen_Calculate(const BcmInput_t* in, BcmOutput_t* out);
void BCM_Ebd_PerformSplit(const BcmInput_t* in, BcmOutput_t* out);
void BCM_Hsa_RunStateMachine(const BcmInput_t* in, BcmOutput_t* out);
void BCM_Safety_Check(const BcmInput_t* in, BcmOutput_t* out);
void BCM_Wiping_Rain(const BcmInput_t* in, BcmOutput_t* out);
void BCM_Eba_RunAssist(const BcmInput_t* in, BcmOutput_t* out);
void BCM_Diag_Update(BcmOutput_t* out);
BcmStatus_t BCM_HwMon_CheckHardware(const BcmInput_t* in);

/* Reset functions for unit testing */
void BCM_Safety_Reset(void);
void BCM_Wiping_Reset(void);
void BCM_Test_ResetAll(void);

#endif /* BCM_INTERNAL_H */
