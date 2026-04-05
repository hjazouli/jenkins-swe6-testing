#include "schm.h"
#include <stdio.h>
#include <time.h>

static clock_t last_tick = 0;

/**
 * BSW Scheduler: Simulated Cyclic Task triggering
 */
void Timer_10ms_Start(void) {
    last_tick = clock();
}

uint8_t Timer_Check_10ms_Tick(void) {
    clock_t current_tick = clock();
    double elapsed_ms = (double)(current_tick - last_tick) * 1000.0 / CLOCKS_PER_SEC;

    if (elapsed_ms >= 10.0) {
        last_tick = current_tick;
        return 1;
    }
    return 0;
}
