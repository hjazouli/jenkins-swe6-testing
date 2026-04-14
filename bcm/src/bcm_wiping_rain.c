#include "bcm_cfg.h"
#include "bcm_types.h"
#include <stdint.h>
#include <stdbool.h>

/** @brief Active wiping duration (1.0s = 100 cycles) */
static uint16_t s_wiping_active_cnt = 100;
/** @brief Total period cycle (60.0s = 6000 cycles) */
static uint16_t s_wiping_period_cnt = 6000;

/**
 * @brief Logic for Disc Wiping ADAS feature.
 * @req SSR_ADA_002
 */
void BCM_Wiping_Rain(const BcmInput_t* in, BcmOutput_t* out) {
  if (in->rain_detected && in->vehicle_speed > 50.0f) {
    if (s_wiping_active_cnt > 0) {
      /* Apply 2.0 Bar only if driver is not already braking harder */
      if (out->hydraulic_pressure < 2.0f) {
        out->hydraulic_pressure = 2.0f;
      }
      s_wiping_active_cnt--;
    } else {
      /* Pulse finished, wait for the rest of the 60s period */
      if (s_wiping_period_cnt > 0) {
        s_wiping_period_cnt--;
      } else {
        /* Period finished, reset both counters */
        s_wiping_active_cnt = 100;
        s_wiping_period_cnt = 6000;
      }
    }
  } else {
    /* If rain stops or speed drops, reset timers for next time */
    s_wiping_active_cnt = 100;
    s_wiping_period_cnt = 6000;
  }
}

/**
 * @brief Reset wiping timers (for testing).
 */
void BCM_Wiping_Reset(void) {
  s_wiping_active_cnt = 100;
  s_wiping_period_cnt = 6000;
}