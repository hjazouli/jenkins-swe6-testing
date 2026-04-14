#include "bcm/bcm_types.h"
#include <stdint.h>

#define MAX_LOG_ENTRIES 5

typedef struct {
    uint32_t frame_id;
    uint8_t  bit_id;
} LogEntry_t;

static LogEntry_t s_fault_log[MAX_LOG_ENTRIES];
static uint8_t    s_log_index = 0;
static uint8_t    s_prev_status = 0;
static uint32_t   s_frame_counter = 0;

/**
 * @brief Records safety events into a circular buffer.
 * @req SWE_REQ_018
 */
void BCM_Logger_Run(const BcmOutput_t* out) {
    s_frame_counter++;

    /* 
     * TODO: Detect which bit was JUST set (rising edge).
     * If a new bit is found, add to s_fault_log[s_log_index] 
     * and increment s_log_index (wrap at 5).
     */
    
    s_prev_status = out->status_flag;
}

void BCM_Logger_Reset(void) {
    s_log_index = 0;
    s_prev_status = 0;
    s_frame_counter = 0;
    for(int i=0; i<MAX_LOG_ENTRIES; i++) {
        s_fault_log[i].frame_id = 0;
        s_fault_log[i].bit_id = 0;
    }
}
