#ifndef BCM_CFG_H
#define BCM_CFG_H

/**
 * @file bcm_cfg.h
 * @brief Calibration and configuration thresholds for the BCM.
 */

/* ========================================================================= */
/*                          CALIBRATION PARAMETERS                            */
/* ========================================================================= */

/** @brief Factor to reduce pressure during ABS event [Ratio] */
#define BCM_CFG_ABS_PRESSURE_REDUCTION_FACTOR 0.62f

/** @brief Conversion ratio from motor torque to hydraulic pressure [1 Bar = 10
 * Nm] */
#define BCM_CFG_REGEN_TORQUE_TO_BAR_RATIO 10.0f

/** @brief Threshold to trigger overheat warning [Celsius] */
#define BCM_CFG_BRAKE_OVERHEAT_THRESHOLD_C 200.0f

/** @brief Maximum pressure allowed when overheat is active [Bar] */
#define BCM_CFG_THERMAL_CLAMP_MAX_PRESSURE 50.0f

/** @brief Pressure to maintain during Hill Start [Bar] */
#define BCM_CFG_HSA_HOLD_PRESSURE 30.0f

/** @brief Time to hold pressure in HSA [Ticks, 1 Tick = 10ms] */
#define BCM_CFG_HSA_HOLD_DURATION_CYCLES 200

/** @brief Speed above which EBD/HSA releases [km/h] */
#define BCM_CFG_RELEASE_SPEED_THRESHOLD 5.0f

/** @brief Deceleration threshold to trigger EBD split [m/s^2] */
#define BCM_CFG_EBD_DECEL_THRESHOLD 5.0f

/** @brief EBD Rear pressure ratio relative to front [Ratio] */
#define BCM_CFG_EBD_REAR_PRESSURE_RATIO 0.7f

#endif /* BCM_CFG_H */
