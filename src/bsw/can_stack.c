#include "can_stack.h"
#include <stdio.h>
#include <string.h>

/* Mock CAN buffer for unit testing/simulation */
static BrakeInput_t mock_can_input = {0};

/**
 * BSW: Simulated CAN Driver Layer
 * This would normally interact with hardware registers.
 */
void CAN_Init(void) {
    printf("[BSW] CAN Bus initialized and listening...\n");
    memset(&mock_can_input, 0, sizeof(BrakeInput_t));
}

/**
 * CAN_Read_Brake_Pedal:
 * In a real ECU, this would pull bytes from the CAN Rx FIFO and unpack them.
 * Here, we read from the static mock buffer.
 */
void CAN_Read_Brake_Pedal(BrakeInput_t* input) {
    if (input != NULL) {
        *input = mock_can_input;
    }
}

/**
 * CAN_Write_Status:
 * Simulated Transmission. In a real system, this would pack the struct into
 * a CAN frame and write to the Tx request register.
 */
void CAN_Write_Status(const BrakeOutput_t* output) {
    (void)output; /* Avoid unused parameter warning */
}

/* --- Internal Test Hooks (Not part of public header) --- */
void Mock_CAN_Set_Input(const BrakeInput_t* input) {
    if (input != NULL) {
        mock_can_input = *input;
    }
}
