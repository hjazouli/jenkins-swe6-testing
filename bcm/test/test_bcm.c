#include "bcm_iface.h"
#include "unity.h"

/* Helper to setup test environment */
void setUp(void) {}
void tearDown(void) {}

/**
 * @brief Normal braking scenario.
 */
void test_BCM_Step_NormalBraking(void) {
  BcmInput_t input = {.pedal_force = 50.0f, .vehicle_speed = 60.0f};
  BcmOutput_t output;

  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* Should map 1:1 since ABS is inactive */
  TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
  TEST_ASSERT_EQUAL_UINT8(0, output.abs_active);
}

/**
 * @brief ABS Activation scenario (High speed, hard braking).
 */
void test_BCM_Step_ABSActivation(void) {
  BcmInput_t input = {.pedal_force = 90.0f, .vehicle_speed = 110.0f};
  BcmOutput_t output;

  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* 90 * 0.62 = 55.8 Bar */
  TEST_ASSERT_EQUAL_FLOAT(55.8f, output.hydraulic_pressure);
  TEST_ASSERT_EQUAL_UINT8(1, output.abs_active);
}

/**
 * @brief Hill Start Assist Lifecycle (SWE_REQ_009).
 */
void test_BCM_Step_HillStartLifecycle(void) {
  BcmInput_t input = {.pedal_force = 90.0f, .vehicle_speed = 0.0f};
  BcmOutput_t output;

  BCM_Init(&output);

  /* 1. Arm */
  BCM_Step(&input, &output);

  /* 2. Release - Should hold 30 Bar */
  input.pedal_force = 0.0f;
  BCM_Step(&input, &output);
  TEST_ASSERT_EQUAL_FLOAT(30.0f, output.hydraulic_pressure);

  /* 3. Timeout check (2s) */
  for (int i = 0; i < 201; i++) BCM_Step(&input, &output);
  TEST_ASSERT_EQUAL_FLOAT(0.0f, output.hydraulic_pressure);
}

/**
 * @brief EBD Distribution (SWE_REQ_013).
 */
void test_BCM_Step_EBDActivation(void) {
  BcmInput_t input = {.pedal_force = 50.0f, .vehicle_speed = 100.0f};
  BcmOutput_t output;

  BCM_Init(&output);

  /* Frame 1: Baseline */
  BCM_Step(&input, &output);

  /* Frame 2: Deceleration > 5m/s2 (100 -> 80 in 10ms) */
  input.vehicle_speed = 80.0f;
  BCM_Step(&input, &output);

  /* Rear = 70% of Front (50 * 0.7 = 35) */
  TEST_ASSERT_EQUAL_FLOAT(50.0f, output.front_hydraulic_pressure);
  TEST_ASSERT_EQUAL_FLOAT(35.0f, output.rear_hydraulic_pressure);
}

/**
 * @brief Thermal Safety and Clamping (SWE_REQ_007/008).
 */
void test_BCM_Step_ThermalSafety(void) {
  BcmInput_t input = {.pedal_force = 80.0f,
                      .vehicle_speed = 40.0f,
                      .brake_temp_celsius = 250.0f};
  BcmOutput_t output;

  BCM_Init(&output);

  /* Trigger overheat */
  BCM_Step(&input, &output);
  
  /* Bit 1 should be set, pressure clamped to 50 */
  TEST_ASSERT_BIT_HIGH(1, output.status_flag);
  TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
}

/**
 * @brief Regen Blending (SWE_REQ_014).
 */
void test_BCM_Step_RegenBlending(void) {
  BcmInput_t input = {.pedal_force = 50.0f, .motor_torque = 100.0f};
  BcmOutput_t output;

  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* 50 Bar - (100 / 10) = 40 Bar */
  TEST_ASSERT_EQUAL_FLOAT(40.0f, output.hydraulic_pressure);
}

/**
 * @brief Heartbeat counter (SWE_REQ_015).
 */
void test_BCM_Step_Heartbeat(void) {
  BcmInput_t input = {0};
  BcmOutput_t output;

  BCM_Init(&output);
  
  BCM_Step(&input, &output);
  uint8_t hb1 = (output.status_flag >> 5) & 0x07;
  
  BCM_Step(&input, &output);
  uint8_t hb2 = (output.status_flag >> 5) & 0x07;

  TEST_ASSERT_EQUAL_UINT8((hb1 + 1) & 0x07, hb2);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_BCM_Step_NormalBraking);
  RUN_TEST(test_BCM_Step_ABSActivation);
  RUN_TEST(test_BCM_Step_HillStartLifecycle);
  RUN_TEST(test_BCM_Step_EBDActivation);
  RUN_TEST(test_BCM_Step_ThermalSafety);
  RUN_TEST(test_BCM_Step_RegenBlending);
  RUN_TEST(test_BCM_Step_Heartbeat);
  return UNITY_END();
}
