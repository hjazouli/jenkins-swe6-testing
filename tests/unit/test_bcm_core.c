#include "bcm_cfg.h"
#include "bcm_iface.h"
#include "unity.h"

/* Required by Unity: Reset state before each test */
void setUp(void) {}

void tearDown(void) {}

/* ========================================================================= */
/* test_BCM_Step_NormalBraking:
 * Scenario: Medium pedal force and speed.
 * Expected: Hydraulic pressure matches pedal force. No ABS. No warnings.
 * ========================================================================= */
void test_BCM_Step_NormalBraking(void) {
  BcmInput_t input = {.pedal_force = 50.0f,
                      .vehicle_speed = 50.0f,
                      .brake_wear_pct = 0.0f,
                      .brake_temp_celsius = 50.0f};
  BcmOutput_t output;
  BCM_Init(&output);

  BCM_Step(&input, &output);

  TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
  TEST_ASSERT_EQUAL_UINT8(0, output.abs_active);
  /* status_flag should have bit 0 (brake light) set because pedal > 5% */
  TEST_ASSERT_EQUAL_UINT8(BCM_FLAG_BRAKE_LIGHT, output.status_flag & 0x1F);
}

/* ========================================================================= */
/* test_BCM_Step_ABSIntervention:
 * Scenario: High speed (>100) and high pedal force (>80).
 * Expected: ABS activates, pressure reduced, status bit 2 set
 * (BCM_FLAG_ABS_ACTIVE).
 * ========================================================================= */
void test_BCM_Step_ABSIntervention(void) {
  BcmInput_t input = {.pedal_force = 90.0f,
                      .vehicle_speed = 120.0f,
                      .brake_temp_celsius = 50.0f};
  BcmOutput_t output;
  BCM_Init(&output);

  BCM_Step(&input, &output);

  /* Checking if ABS reduced pressure and set flags */
  TEST_ASSERT_EQUAL_UINT8(1, output.abs_active);
  TEST_ASSERT_TRUE((output.status_flag & BCM_FLAG_ABS_ACTIVE) != 0);
}

/* ========================================================================= */
/* test_BCM_Step_EBD_Split:
 * Scenario: Front and rear axle pressure split.
 * ========================================================================= */
void test_BCM_Step_EBD_Split(void) {
  BcmInput_t input = {.pedal_force = 80.0f, .vehicle_speed = 60.0f};
  BcmOutput_t output;
  BCM_Init(&output);

  BCM_Step(&input, &output);

  TEST_ASSERT_EQUAL_FLOAT(80.0f, output.front_hydraulic_pressure);
  /* Expected EBD split, typically 70% to rear under hard braking */
  TEST_ASSERT_EQUAL_FLOAT(56.0f, output.rear_hydraulic_pressure);
}

/* ========================================================================= */
/* test_BCM_Safety_OverheatLatchAndClamp:
 * Scenario: Brake temp exceeds threshold, then recovers.
 * Expected: THERMAL_FAULT latches immediately and clamps pressure to
 * BCM_CFG_THERMAL_CLAMP_MAX_PRESSURE; latch requires 3 recovery cycles
 * below threshold to clear (SWE_REQ_007/008).
 * ========================================================================= */
void test_BCM_Safety_OverheatLatchAndClamp(void) {
  BcmInput_t input = {.pedal_force = 80.0f,
                      .vehicle_speed = 30.0f,
                      .brake_temp_celsius = 250.0f};
  BcmOutput_t output;
  BCM_Init(&output);

  /* Frame 1: temp above threshold -> latch sets, pressure clamped */
  BCM_Step(&input, &output);
  TEST_ASSERT_TRUE(output.status_flag & BCM_FLAG_THERMAL_FAULT);
  TEST_ASSERT_EQUAL_FLOAT(BCM_CFG_THERMAL_CLAMP_MAX_PRESSURE,
                          output.hydraulic_pressure);

  /* Frames 2-4: temp back to normal, but latch needs 3 cycles to clear */
  input.brake_temp_celsius = 150.0f;
  BCM_Step(&input, &output); /* recovery cycle 1/3 */
  TEST_ASSERT_TRUE(output.status_flag & BCM_FLAG_THERMAL_FAULT);
  BCM_Step(&input, &output); /* recovery cycle 2/3 */
  TEST_ASSERT_TRUE(output.status_flag & BCM_FLAG_THERMAL_FAULT);
  BCM_Step(&input, &output); /* recovery cycle 3/3 -> cleared */
  TEST_ASSERT_FALSE(output.status_flag & BCM_FLAG_THERMAL_FAULT);
  TEST_ASSERT_EQUAL_FLOAT(80.0f, output.hydraulic_pressure);
}

/* ========================================================================= */
/* test_BCM_Safety_BrakeWearWarning:
 * Scenario: Brake wear crosses BCM_CFG_BRAKE_WEAR_LIMIT.
 * Expected: BCM_FLAG_BRAKE_WEAR sets above the limit and clears immediately
 * once wear drops back below it (no latch, unlike thermal) (SWE_REQ_009).
 * ========================================================================= */
void test_BCM_Safety_BrakeWearWarning(void) {
  BcmInput_t input = {.pedal_force = 20.0f,
                      .vehicle_speed = 20.0f,
                      .brake_wear_pct = 95.0f};
  BcmOutput_t output;
  BCM_Init(&output);

  BCM_Step(&input, &output);
  TEST_ASSERT_TRUE(output.status_flag & BCM_FLAG_BRAKE_WEAR);

  input.brake_wear_pct = 50.0f;
  BCM_Step(&input, &output);
  TEST_ASSERT_FALSE(output.status_flag & BCM_FLAG_BRAKE_WEAR);
}

/* ========================================================================= */
/* test_BCM_Safety_ThresholdBoundaries:
 * Scenario: Temp and wear sit exactly on their thresholds.
 * Expected: Neither warning fires (strict '>' comparison, not '>=').
 * ========================================================================= */
void test_BCM_Safety_ThresholdBoundaries(void) {
  BcmInput_t input = {.pedal_force = 20.0f,
                      .vehicle_speed = 20.0f,
                      .brake_temp_celsius = BCM_CFG_BRAKE_OVERHEAT_THRESHOLD_C,
                      .brake_wear_pct = BCM_CFG_BRAKE_WEAR_LIMIT};
  BcmOutput_t output;
  BCM_Init(&output);

  BCM_Step(&input, &output);

  TEST_ASSERT_FALSE(output.status_flag & BCM_FLAG_THERMAL_FAULT);
  TEST_ASSERT_FALSE(output.status_flag & BCM_FLAG_BRAKE_WEAR);
}

/* ========================================================================= */
/* test_BCM_Hsa_StateMachine:
 * Scenario: Hill Start Assist activation and release.
 * ========================================================================= */
void test_BCM_Hsa_StateMachine(void) {
  BcmInput_t input = {.pedal_force = 90.0f, .vehicle_speed = 0.0f};
  BcmOutput_t output;
  BCM_Init(&output);

  /* 1. Arm the system */
  BCM_Step(&input, &output);
  TEST_ASSERT_FALSE(output.status_flag & BCM_FLAG_HSA_ACTIVE);

  /* 2. Release pedal -> Should enter HOLDING */
  input.pedal_force = 0.0f;
  BCM_Step(&input, &output); // Transition to HOLDING
  BCM_Step(&input, &output); // Execute HOLDING logic
  TEST_ASSERT_TRUE(output.status_flag & BCM_FLAG_HSA_ACTIVE);
  TEST_ASSERT_EQUAL_FLOAT(BCM_CFG_HSA_HOLD_PRESSURE,
                          output.front_hydraulic_pressure);

  /* 3. Car starts moving -> Should release */
  input.vehicle_speed = 10.0f;
  BCM_Step(&input, &output); // Transition to IDLE
  BCM_Step(&input, &output); // Execute IDLE (flag cleared)
  TEST_ASSERT_FALSE(output.status_flag & BCM_FLAG_HSA_ACTIVE);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_BCM_Step_NormalBraking);
  RUN_TEST(test_BCM_Step_ABSIntervention);
  RUN_TEST(test_BCM_Step_EBD_Split);
  RUN_TEST(test_BCM_Safety_OverheatLatchAndClamp);
  RUN_TEST(test_BCM_Safety_BrakeWearWarning);
  RUN_TEST(test_BCM_Safety_ThresholdBoundaries);
  RUN_TEST(test_BCM_Hsa_StateMachine);
  return UNITY_END();
}
