#include "unity.h"
#include "bsw/schm.h"
#include <time.h>
#include <unistd.h>

/* Required by Unity */
void setUp(void) {}
void tearDown(void) {}

/**
 * test_Timer_InitialState:
 * Initial check should return 0 before it's started or right after start.
 */
void test_Timer_InitialState(void) {
    Timer_10ms_Start();
    TEST_ASSERT_EQUAL_UINT8(0, Timer_Check_10ms_Tick());
}

/**
 * test_Timer_TickAfterDelay:
 * Check that the timer returns 1 after waiting at least 10ms.
 */
void test_Timer_TickAfterDelay(void) {
    Timer_10ms_Start();
    
    /* Wait for ~15ms to be safe */
    usleep(15000); 
    
    /* Note: Timer_Check_10ms_Tick uses clock() which measures CPU time.
     * In some environments, usleep might not consume enough 'clock' cycles.
     * However, for a simple simulation, we expect it to eventually tick.
     */
     
    /* Since we are in a unit test environment, we might need to simulate 
     * CPU cycles or just wait long enough. 
     * Let's try to busy-wait if clock doesn't advance with usleep.
     */
    clock_t start = clock();
    while (((double)(clock() - start) * 1000.0 / CLOCKS_PER_SEC) < 11.0);
    
    TEST_ASSERT_EQUAL_UINT8(1, Timer_Check_10ms_Tick());
}

/**
 * test_Timer_ResetAfterTick:
 * After a tick is detected, the next immediate check should be 0.
 */
void test_Timer_ResetAfterTick(void) {
    Timer_10ms_Start();
    
    /* Busy wait for 11ms */
    clock_t start = clock();
    while (((double)(clock() - start) * 1000.0 / CLOCKS_PER_SEC) < 11.0);
    
    /* First call should return 1 */
    TEST_ASSERT_EQUAL_UINT8(1, Timer_Check_10ms_Tick());
    
    /* Immediate second call should return 0 */
    TEST_ASSERT_EQUAL_UINT8(0, Timer_Check_10ms_Tick());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_Timer_InitialState);
    RUN_TEST(test_Timer_TickAfterDelay);
    RUN_TEST(test_Timer_ResetAfterTick);
    return UNITY_END();
}
