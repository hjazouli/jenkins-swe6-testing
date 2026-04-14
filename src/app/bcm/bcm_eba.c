#include "bcm/bcm_cfg.h"
#include "bcm/bcm_types.h"

/**
 * @brief Logic for Emergency Brake Assist (EBA).
 * @req SWE_REQ_010
 */
void BCM_Eba_RunAssist(const BcmInput_t* in, BcmOutput_t* out) {
    /* Condition: Pedal slam (>90%) at high speed (>60 km/h) */
    if (in->pedal_force > 90.0f && in->vehicle_speed > 60.0f) {
        /* Boost to maximum platform pressure */
        if (out->hydraulic_pressure < 100.0f) {
            out->hydraulic_pressure = 100.0f;
        }
    }
}
