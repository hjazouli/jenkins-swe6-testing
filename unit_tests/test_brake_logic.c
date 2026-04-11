#include "unity.h"
#include "app/brake_logic.h"

/* Required by Unity: Reset state before each test */
void setUp(void) {
    BrakeOutput_t dummy;
    Brake_Control_Init(&dummy);
}

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
        .sensor_wear_volt = 4.6f, 
        .brake_temp_celsius = 250.0f 
    };
    BrakeOutput_t output;
    
    Brake_Control_Step(&input, &output);
    
    TEST_ASSERT_EQUAL_UINT8(0x0A, output.status_flag); 
}

/**
 * test_Brake_Control_Step_ThresholdBoundaries:
 * Scenario: Values exactly on the threshold.
 */
void test_Brake_Control_Step_ThresholdBoundaries(void) {
    BrakeInput_t input = { .pedal_force = 10.0f, .vehicle_speed = 10.0f };
    BrakeOutput_t output;

    input.sensor_wear_volt = 4.5f;
    input.brake_temp_celsius = 150.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_BIT_LOW(3, output.status_flag);
}

/**
 * test_Brake_Control_Step_Clamping:
 * Scenario: OOB inputs.
 */
void test_Brake_Control_Step_Clamping(void) {
    BrakeInput_t input = { .vehicle_speed = 50.0f };
    BrakeOutput_t output;
    
    input.pedal_force = 150.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_FLOAT(100.0f, output.hydraulic_pressure);
}

/**
 * test_Brake_Control_Step_DebounceRecovery:
 * Scenario: Overheat occurs, then temperature drops. 
 */
void test_Brake_Control_Step_DebounceRecovery(void) {
    BrakeInput_t input = { .pedal_force = 10.0f };
    BrakeOutput_t output;

    input.brake_temp_celsius = 250.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_BIT_HIGH(1, output.status_flag);

    input.brake_temp_celsius = 150.0f;
    Brake_Control_Step(&input, &output); // Cycle 1 (Latched)
    TEST_ASSERT_BIT_HIGH(1, output.status_flag);
    
    Brake_Control_Step(&input, &output); // Cycle 2 (Latched)
    Brake_Control_Step(&input, &output); // Cycle 3 (Cleared)
    TEST_ASSERT_BIT_LOW(1, output.status_flag);
}

/** 
* test_Brake_Control_Step_StuckPedal:
* Scenario: Pedal > 50% while speed is not decreasing.
* Requirement: 5 frames to trigger, 3 frames of continuous decrease to clear.
*/
void test_Brake_Control_Step_StuckPedal(void) {
    BrakeInput_t input = { .pedal_force = 90.0f, .vehicle_speed = 100.0f };
    BrakeOutput_t output;

    /* 1. Trigger Fault (Must run 5 cycles where speed NOT decreasing) */
    for(int i=0; i<4; i++) {
        Brake_Control_Step(&input, &output);
        TEST_ASSERT_BIT_LOW(4, output.status_flag);
    }
    Brake_Control_Step(&input, &output); // 5th Cycle
    TEST_ASSERT_BIT_HIGH(4, output.status_flag); // FAULT!

    /* 2. Recovery: Speed must decrease (input < last) for 3 cycles */
    input.vehicle_speed = 90.0f;
    Brake_Control_Step(&input, &output); // Cycle 1 (90 < 100: Latched)
    TEST_ASSERT_BIT_HIGH(4, output.status_flag);

    input.vehicle_speed = 80.0f;
    Brake_Control_Step(&input, &output); // Cycle 2 (80 < 90: Latched)
    TEST_ASSERT_BIT_HIGH(4, output.status_flag);

    input.vehicle_speed = 70.0f;
    Brake_Control_Step(&input, &output); // Cycle 3 (70 < 80: Cleared)
    TEST_ASSERT_BIT_LOW(4, output.status_flag);
}   

/**
 * test_Brake_Control_Step_EmergencyStopAssistance:
 * Scenario: Pedal > 90% and Speed > 60 km/h.
 * Expected: Pressure is boosted to 100.0 Bar.
 */
void test_Brake_Control_Step_EmergencyStopAssistance(void) {
    BrakeInput_t input = { 
        .pedal_force = 91.0f, 
        .vehicle_speed = 65.0f, 
        .wheel_speed = 65.0f 
    };
    BrakeOutput_t output;
    
    Brake_Control_Step(&input, &output);
    
    TEST_ASSERT_EQUAL_FLOAT(100.0f, output.hydraulic_pressure);
}

/**
 * test_Brake_Control_Step_ThermalSafetyClamp:
 * Scenario: Overheat bit is set (from previous frame) and pressure is high.
 * Expected: Pressure clamped to 50.0 Bar.
 */
void test_Brake_Control_Step_ThermalSafetyClamp(void) {
    BrakeInput_t input = { .pedal_force = 80.0f, .vehicle_speed = 30.0f, .brake_temp_celsius = 250.0f };
    BrakeOutput_t output;

    /* Frame 1: Set overheat latch */
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_BIT_HIGH(1, output.status_flag);
    
    /* Frame 2: Pressure should be clamped even if pedal asks for 80 */
    input.brake_temp_celsius = 150.0f; // Still latched
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
    TEST_ASSERT_BIT_HIGH(1, output.status_flag);
}

/**
 * test_Brake_Control_Step_SafetyPriority:
 * Scenario: Both ESA and Overheat are active.
 * Expected: Thermal Clamp wins over ESA (50 Bar vs 100 Bar).
 */
void test_Brake_Control_Step_SafetyPriority(void) {
    BrakeInput_t input = { 
        .pedal_force = 95.0f, 
        .vehicle_speed = 70.0f, 
        .brake_temp_celsius = 250.0f 
    };
    BrakeOutput_t output;

    /* Frame 1: Trigger ESA and Overheat */
    Brake_Control_Step(&input, &output);
    /* In frame 1, ESA sets 100, then Thermal_Safety_Clamp sees bit 1 is set in status_flag 
       (because Fault_Latching_Overheat was called before it). So it should clamp. */
    TEST_ASSERT_EQUAL_FLOAT(50.0f, output.hydraulic_pressure);
    TEST_ASSERT_BIT_HIGH(1, output.status_flag);
}

/**
 * test_Brake_Control_Step_NullPointers:
 * Scenario: Passing NULL to the step function.
 * Expected: Function returns gracefully without crash.
 */
void test_Brake_Control_Step_NullPointers(void) {
    BrakeInput_t input = { .pedal_force = 50.0f };
    BrakeOutput_t output;

    /* Should not crash */
    Brake_Control_Step(NULL, &output);
    Brake_Control_Step(&input, NULL);
    Brake_Control_Step(NULL, NULL);
}

/**
 * test_Brake_Control_Step_NegativeClamping:
 * Scenario: Pedal force is negative.
 * Expected: Clamped to 0.
 */
void test_Brake_Control_Step_NegativeClamping(void) {
    BrakeInput_t input = { .pedal_force = -50.0f };
    BrakeOutput_t output;
    
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, output.hydraulic_pressure);
}

/**
 * test_Brake_Control_Init_ResetsInternalState:
 * Scenario: Force a fault, then call Init.
 * Expected: Fault is cleared in next step.
 */
void test_Brake_Control_Init_ResetsInternalState(void) {
    BrakeInput_t input = { .pedal_force = 10.0f, .brake_temp_celsius = 250.0f };
    BrakeOutput_t output;

    /* 1. Trigger overheat latch */
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_BIT_HIGH(1, output.status_flag);

    /* 2. Init */
    Brake_Control_Init(&output);
    TEST_ASSERT_EQUAL_UINT8(0, output.status_flag);

    /* 3. New step with safe temp - should NOT have latch anymore */
    input.brake_temp_celsius = 100.0f;
    Brake_Control_Step(&input, &output);
    TEST_ASSERT_BIT_LOW(1, output.status_flag);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_Brake_Control_Step_NormalBraking);
    RUN_TEST(test_Brake_Control_Step_ABSIntervention);
    RUN_TEST(test_Brake_Control_Step_ABSEdgeCases);
    RUN_TEST(test_Brake_Control_Step_Warnings);
    RUN_TEST(test_Brake_Control_Step_ThresholdBoundaries);
    RUN_TEST(test_Brake_Control_Step_Clamping);
    RUN_TEST(test_Brake_Control_Step_DebounceRecovery);
    RUN_TEST(test_Brake_Control_Step_StuckPedal);
    RUN_TEST(test_Brake_Control_Step_EmergencyStopAssistance);
    RUN_TEST(test_Brake_Control_Step_ThermalSafetyClamp);
    RUN_TEST(test_Brake_Control_Step_SafetyPriority);
    RUN_TEST(test_Brake_Control_Step_NullPointers);
    RUN_TEST(test_Brake_Control_Step_NegativeClamping);
    RUN_TEST(test_Brake_Control_Init_ResetsInternalState);
    return UNITY_END();
}
