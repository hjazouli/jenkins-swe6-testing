#include "bcm/bcm_cfg.h"
#include "bcm/bcm_types.h"
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>

static float vehicle_last_speed = 0.0f;
static uint8_t stuck_counter = 0;
static uint8_t recovery_counter = 0;
static bool fault_active = false;

/**
 * @brief Plausibility Check for Stuck Pedal detection.
 * @req SWE_REQ_011
 */
void BCM_Plausibility_Check(const BcmInput_t* in, BcmOutput_t* out) {
    /* 1. Detection Logic: If braking but speed is not decreasing */
    if (in->pedal_force > 50.0f && in->vehicle_speed >= vehicle_last_speed) {
        stuck_counter++;
    } else {
        stuck_counter = 0;
    }

    /* 2. Latch Fault after 5 frames */
    if (stuck_counter >= 5) {
        fault_active = true;
    }

    /* 3. Recovery Logic: If fault is active, look for speed decrease */
    if (fault_active) {
        if (in->vehicle_speed < vehicle_last_speed) {
            recovery_counter++;
        } else {
            recovery_counter = 0;
        }

        /* Clear fault after 3 consecutive frames of decrease */
        if (recovery_counter >= 3) {
            fault_active = false;
            recovery_counter = 0;
            stuck_counter = 0;
        }
    }

    /* 4. Update Status Flag [Bit 2] */
    if (fault_active) {
        out->status_flag |= (1 << 2);
    } else {
        out->status_flag &= ~(1 << 2);
    }

    /* 5. Update state for next cycle */
    vehicle_last_speed = in->vehicle_speed;
}

/**
 * @brief Reset internal state for unit testing.
 */
void BCM_Plausibility_Reset(void) {
    stuck_counter = 0;
    recovery_counter = 0;
    fault_active = false;
    vehicle_last_speed = 0.0f;
}
