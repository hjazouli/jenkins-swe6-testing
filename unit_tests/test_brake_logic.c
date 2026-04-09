#include "unity.h"
#include "app/brake_logic.h"

/* Required by Unity */
void setUp(void) {}
void tearDown(void) {}

/**
 * test_Brake_Control_Step_NormalBraking:
 * Scenario: Medium pedal force and speed. 
 * Expected: Hydraulic pressure matches pedal force. No ABS. No warnings.
 */
void test_Brake_Control_Step_NormalBraking(void) {
    BrakeInput_t input = { 
        .pedal_force = 50.0f, 
        .vehicle_speed = 50.0f, 
        .wheel_speed = 50.0f, 
        .sensor_wear_volt = 1.0f, 
        .brake_temp_celsius = 50.0f 
    };
    BrakeOutput_t output;
    
    Brake_Control_Step(&input, &output);
    
    TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
    TEST_ASSERT_EQUAL_UINT8(0, output.abs_active);
    TEST_ASSERT_EQUAL_UINT8(0, output.status_flag);
}

/**
 * test_Brake_Control_Step_ABSIntervention:
 * Scenario: High speed (>100) and high pedal force (>80).
 * Expected: ABS activates, pressure reduced, status bit 0 set.
 */
void test_Brake_Control_Step_ABSIntervention(void) {
    BrakeInput_t input = { 
        .pedal_force = 90.0f, 
        .vehicle_speed = 120.0f, 
        .wheel_speed = 80.0f, 
        .sensor_wear_volt = 1.0f, 
        .brake_temp_celsius = 50.0f 
    };
    BrakeOutput_t output;
    
    Brake_Control_Step(&input, &output);
    
    TEST_ASSERT_EQUAL_FLOAT(90.0f * ABS_PRESSURE_REDUCTION_FACTOR, output.hydraulic_pressure);
    TEST_ASSERT_EQUAL_UINT8(1, output.abs_active);
    TEST_ASSERT_BIT_HIGH(0, output.status_flag); 
}

/**
 * test_Brake_Control_Step_ABSEdgeCases:
 * Scenario: Testing exact boundaries for ABS (100km/h, 80% pedal).
 * Expected: ABS only activates ABOVE these thresholds.
 */
void test_Brake_Control_Step_ABSEdgeCases(void) {
    BrakeInput_t input = { .sensor_wear_volt = 1.0f, .brake_temp_celsius = 50.0f };
    BrakeOutput_t output;

    /* speed = 100, pedal = 80 -> NO ABS */
    input.vehicle_speed = 100.0f;
    input.pedal_force = 80.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_UINT8(0, output.abs_active);

    /* speed = 100.1, pedal = 80 -> NO ABS */
    input.vehicle_speed = 100.1f;
    input.pedal_force = 80.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_UINT8(0, output.abs_active);

    /* speed = 100, pedal = 80.1 -> NO ABS */
    input.vehicle_speed = 100.0f;
    input.pedal_force = 80.1f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_UINT8(0, output.abs_active);

    /* speed = 100.1, pedal = 80.1 -> ABS ACTIVE */
    input.vehicle_speed = 100.1f;
    input.pedal_force = 80.1f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_UINT8(1, output.abs_active);
}

/**
 * test_Brake_Control_Step_Warnings:
 * Scenario: Voltage and temperature above thresholds.
 * Expected: Warning bits set correctly (Bit 1 for Overheat, Bit 3 for Wear).
 */
void test_Brake_Control_Step_Warnings(void) {
    BrakeInput_t input = { 
        .pedal_force = 10.0f, 
        .vehicle_speed = 10.0f, 
        .wheel_speed = 10.0f, 
        .sensor_wear_volt = 4.6f, /* Above 4.5V threshold */
        .brake_temp_celsius = 250.0f /* Above 200C threshold */
    };
    BrakeOutput_t output;
    
    Brake_Control_Step(&input, &output);
    
    /* 0x02 (Overheat) | 0x08 (Wear) = 0x0A */
    TEST_ASSERT_EQUAL_UINT8(0x0A, output.status_flag); 
}

/**
 * test_Brake_Control_Step_ThresholdBoundaries:
 * Scenario: Values exactly on the threshold.
 * Expected: Warning bits only set ABOVE thresholds according to logic.
 */
void test_Brake_Control_Step_ThresholdBoundaries(void) {
    BrakeInput_t input = { .pedal_force = 10.0f, .vehicle_speed = 10.0f };
    BrakeOutput_t output;

    /* Wear at threshold 4.5V */
    input.sensor_wear_volt = 4.5f;
    input.brake_temp_celsius = 150.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_BIT_LOW(3, output.status_flag);

    /* Overheat at threshold 200C */
    input.sensor_wear_volt = 1.0f;
    input.brake_temp_celsius = 200.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_BIT_LOW(1, output.status_flag);
}

/**
 * test_Brake_Control_Step_Clamping:
 * Scenario: OOB inputs (negative and >100%).
 * Expected: Clamped to 0.0 or 100.0 respectively.
 */
void test_Brake_Control_Step_Clamping(void) {
    BrakeInput_t input = { .vehicle_speed = 50.0f, .sensor_wear_volt = 1.0f, .brake_temp_celsius = 50.0f };
    BrakeOutput_t output;
    
    /* Above 100% pedal */
    input.pedal_force = 150.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_FLOAT(100.0f, output.hydraulic_pressure);

    /* Below 0% pedal */
    input.pedal_force = -50.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, output.hydraulic_pressure);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_Brake_Control_Step_NormalBraking);
    RUN_TEST(test_Brake_Control_Step_ABSIntervention);
    RUN_TEST(test_Brake_Control_Step_ABSEdgeCases);
    RUN_TEST(test_Brake_Control_Step_Warnings);
    RUN_TEST(test_Brake_Control_Step_ThresholdBoundaries);
    RUN_TEST(test_Brake_Control_Step_Clamping);
    return UNITY_END();
}
