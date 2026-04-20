#include "unity.h"
#include "bsw/can_stack.h"
#include <string.h>

/* Forward declare the test hook from can_stack.c */
void Mock_CAN_Set_Input(const BrakeInput_t* input);

/* Required by Unity */
void setUp(void) {
    CAN_Init();
}
void tearDown(void) {}

/**
 * test_CAN_Init_ClearsBuffer:
 * Verifies that initializing the CAN stack clears the internal mock buffer.
 */
void test_CAN_Init_ClearsBuffer(void) {
    BrakeInput_t input = { .pedal_force = 50.0f };
    Mock_CAN_Set_Input(&input);
    
    /* Re-init should clear it */
    CAN_Init();
    
    BrakeInput_t read_back = {0};
    CAN_Read_Brake_Pedal(&read_back);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, read_back.pedal_force);
}

/**
 * test_CAN_Read_Brake_Pedal_ReturnsMockData:
 * Verifies that data set via the mock hook is correctly read back.
 */
void test_CAN_Read_Brake_Pedal_ReturnsMockData(void) {
    BrakeInput_t expected = { 
        .pedal_force = 75.5f,
        .vehicle_speed = 120.0f,
        .wheel_speed = 115.0f,
        .sensor_wear_volt = 2.5f,
        .brake_temp_celsius = 98.0f
    };
    
    Mock_CAN_Set_Input(&expected);
    
    BrakeInput_t actual = {0};
    CAN_Read_Brake_Pedal(&actual);
    
    TEST_ASSERT_EQUAL_FLOAT(expected.pedal_force, actual.pedal_force);
    TEST_ASSERT_EQUAL_FLOAT(expected.vehicle_speed, actual.vehicle_speed);
    TEST_ASSERT_EQUAL_FLOAT(expected.brake_temp_celsius, actual.brake_temp_celsius);
}

/**
 * test_CAN_Read_Brake_Pedal_HandlesNull:
 * Safety check for NULL pointer input.
 */
void test_CAN_Read_Brake_Pedal_HandlesNull(void) {
    /* Should not crash */
    CAN_Read_Brake_Pedal(NULL);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_CAN_Init_ClearsBuffer);
    RUN_TEST(test_CAN_Read_Brake_Pedal_ReturnsMockData);
    RUN_TEST(test_CAN_Read_Brake_Pedal_HandlesNull);
    return UNITY_END();
}
