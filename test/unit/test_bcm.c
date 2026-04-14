#include "bcm/bcm_iface.h"
#include "unity.h"

#include "bcm_internal.h"

/* Helper to setup test environment */
void setUp(void) {
  /* Ensure a fresh ECU state before every test */
  BCM_Test_ResetAll();
}
void tearDown(void) {}

/*******************************************************************************
 * TEST: test_BCM_Step_NormalBraking
 * REQ:  Basic Mapping (1:1)
 *******************************************************************************/
void test_BCM_Step_NormalBraking(void) {
  /* pedal_sensor_volt must be in [0.5, 4.5] for system to be active */
  BcmInput_t input = {.pedal_force = 50.0f, .vehicle_speed = 60.0f, .pedal_sensor_volt = 2.5f};
  BcmOutput_t output;

  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* Should map 1:1 since ABS is inactive */
  TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
  TEST_ASSERT_EQUAL_UINT8(0, output.abs_active);
}

/*******************************************************************************
 * TEST: test_BCM_Step_ABSActivation
 * REQ:  SSR_FCN_001
 *******************************************************************************/
void test_BCM_Step_ABSActivation(void) {
  BcmInput_t input = {.pedal_force = 90.0f, .vehicle_speed = 110.0f, .pedal_sensor_volt = 2.5f};
  BcmOutput_t output;

  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* 90 * 0.62 = 55.8 Bar */
  TEST_ASSERT_EQUAL_FLOAT(55.8f, output.hydraulic_pressure);
  TEST_ASSERT_EQUAL_UINT8(1, output.abs_active);
}

/*******************************************************************************
 * TEST: test_BCM_Step_HillStartLifecycle
 * REQ:  SSR_ADA_001
 *******************************************************************************/
void test_BCM_Step_HillStartLifecycle(void) {
  BcmInput_t input = {.pedal_force = 90.0f, .vehicle_speed = 0.0f, .pedal_sensor_volt = 2.5f};
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

/*******************************************************************************
 * TEST: test_BCM_Step_EBDActivation
 * REQ:  SSR_FCN_003
 *******************************************************************************/
void test_BCM_Step_EBDActivation(void) {
  BcmInput_t input = {.pedal_force = 50.0f, .vehicle_speed = 100.0f, .pedal_sensor_volt = 2.5f};
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

/*******************************************************************************
 * TEST: test_BCM_Step_ThermalSafety
 * REQ:  SSR_SAF_003 / SSR_SAF_004
 *******************************************************************************/
void test_BCM_Step_ThermalSafety(void) {
  BcmInput_t input = {.pedal_force = 80.0f,
                      .vehicle_speed = 40.0f,
                      .brake_temp_celsius = 250.0f,
                      .pedal_sensor_volt = 2.5f};
  BcmOutput_t output;

  BCM_Init(&output);

  /* Trigger overheat */
  BCM_Step(&input, &output);

  /* Bit 1 should be set, pressure clamped to 50 */
  TEST_ASSERT_BIT_HIGH(1, output.status_flag);
  TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
}

/*******************************************************************************
 * TEST: test_BCM_Step_RegenBlending
 * REQ:  SSR_FCN_002
 *******************************************************************************/
void test_BCM_Step_RegenBlending(void) {
  BcmInput_t input = {.pedal_force = 50.0f, .motor_torque = 100.0f, .pedal_sensor_volt = 2.5f};
  BcmOutput_t output;

  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* 50 Bar - (100 / 10) = 40 Bar */
  TEST_ASSERT_EQUAL_FLOAT(40.0f, output.hydraulic_pressure);
}

/*******************************************************************************
 * TEST: test_BCM_Step_Heartbeat
 * REQ:  SSR_SYS_002
 *******************************************************************************/
void test_BCM_Step_Heartbeat(void) {
  BcmInput_t input = {.pedal_sensor_volt = 2.5f};
  BcmOutput_t output;

  BCM_Init(&output);

  BCM_Step(&input, &output);
  uint8_t hb1 = (output.status_flag >> 5) & 0x07;

  BCM_Step(&input, &output);
  uint8_t hb2 = (output.status_flag >> 5) & 0x07;

  TEST_ASSERT_EQUAL_UINT8((hb1 + 1) & 0x07, hb2);
}

/*******************************************************************************
 * TEST: test_BCM_Step_SignalQualityFault
 * REQ:  SSR_SAF_002
 *******************************************************************************/
void test_BCM_Step_SignalQualityFault(void) {
  BcmInput_t input = {.pedal_force = 50.0f,
                      .pedal_sensor_volt = 0.2f, /* < 0.5V Fault */
                      .vehicle_speed = 40.0f};
  BcmOutput_t output;

  BCM_Test_ResetAll();
  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* Bit 4 should be set, pressure forced to 0 */
  TEST_ASSERT_BIT_HIGH(4, output.status_flag);
  TEST_ASSERT_EQUAL_FLOAT(0.0f, output.hydraulic_pressure);

  /* Recovery check - High voltage fault */
  input.pedal_sensor_volt = 4.8f; /* > 4.5V Fault */
  BCM_Step(&input, &output);
  TEST_ASSERT_BIT_HIGH(4, output.status_flag);
  TEST_ASSERT_EQUAL_FLOAT(0.0f, output.hydraulic_pressure);
}

/*******************************************************************************
 * TEST: test_BCM_Step_DiscWiping (SSR_ADA_002)
 *******************************************************************************/
void test_BCM_Step_DiscWiping(void) {
  BcmInput_t input = {.pedal_force = 0.0f,
                      .vehicle_speed = 60.0f,
                      .rain_detected = true,
                      .pedal_sensor_volt = 2.5f};
  BcmOutput_t output;

  BCM_Init(&output);

  /* 1. Trigger Pulse - Should apply 2.0 Bar immediately */
  BCM_Step(&input, &output);
  TEST_ASSERT_EQUAL_FLOAT(2.0f, output.hydraulic_pressure);

  /* 2. Check Duration - Should stay at 2.0 Bar for 1.0s (100 cycles) */
  for (int i = 0; i < 99; i++) BCM_Step(&input, &output);
  TEST_ASSERT_EQUAL_FLOAT(2.0f, output.hydraulic_pressure);

  /* 3. Check Release - Cycle 101 should be 0.0 Bar */
  BCM_Step(&input, &output);
  TEST_ASSERT_EQUAL_FLOAT(0.0f, output.hydraulic_pressure);

  /* 4. Check Period - Fast forward rest of the 60s period 
     We need 5999 more cycles to complete the 6000-cycle wait */
  for (int i = 0; i < 5999; i++) BCM_Step(&input, &output);
  
  /* Cycle 6101: Next cycle should start the pulse again */
  BCM_Step(&input, &output);
  TEST_ASSERT_EQUAL_FLOAT(2.0f, output.hydraulic_pressure);
}

/*******************************************************************************
 * TEST: test_BCM_Wiping_Isolation
 *******************************************************************************/
void test_BCM_Wiping_Isolation(void) {
  BcmInput_t input = {.vehicle_speed = 60.0f, .rain_detected = true};
  BcmOutput_t output = {.hydraulic_pressure = 0.0f};

  BCM_Wiping_Reset();
  BCM_Wiping_Rain(&input, &output);

  /* Should set 2.0 Bar directly */
  TEST_ASSERT_EQUAL_FLOAT(2.0f, output.hydraulic_pressure);
}

/*******************************************************************************
 * TEST: test_BCM_Step_EmergencyAssist (SWE_REQ_010)
 *******************************************************************************/
void test_BCM_Step_EmergencyAssist(void) {
  BcmInput_t input = {.pedal_force = 95.0f,    /* Slamming > 90% */
                      .vehicle_speed = 70.0f,  /* Speed > 60 km/h */
                      .pedal_sensor_volt = 3.5f};
  BcmOutput_t output;

  BCM_Init(&output);
  BCM_Step(&input, &output);

  /* Should boost to 100 Bar */
  TEST_ASSERT_EQUAL_FLOAT(100.0f, output.hydraulic_pressure);
}


/*******************************************************************************
 * MAIN: Unity Runner
 *******************************************************************************/
int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_BCM_Step_NormalBraking);
  RUN_TEST(test_BCM_Step_ABSActivation);
  RUN_TEST(test_BCM_Step_HillStartLifecycle);
  RUN_TEST(test_BCM_Step_EBDActivation);
  RUN_TEST(test_BCM_Step_ThermalSafety);
  RUN_TEST(test_BCM_Step_RegenBlending);
  RUN_TEST(test_BCM_Step_Heartbeat);
  RUN_TEST(test_BCM_Step_SignalQualityFault);
  RUN_TEST(test_BCM_Step_DiscWiping);
  RUN_TEST(test_BCM_Wiping_Isolation);
  RUN_TEST(test_BCM_Step_EmergencyAssist);
  return UNITY_END();
}
