#include <stdio.h>
#include "app/brake_logic.h"
#include "bsw/can_stack.h"
#include "bsw/schm.h"

/**
 * ECU Entry Point: Layered Architecture
 * Version v1.3.0 - (ASW/BSW Separated)
 * Target: Infineon TriCore TC397 (Mocked)
 */
int main(void) {
    printf("--- ECU Firmware v1.3.0 Initialized ---\n");
    printf("Target: TC397 (Layered Architecture)\n");
    printf("Brake Logic (ASW) - Active\n");
    printf("CAN Stack (BSW) - Active\n");
    printf("Schedule Manager (BSW) - Active\n");

    // 1. Hardware Initialization (BSW)
    CAN_Init();
    Timer_10ms_Start();

    // 2. Cyclic Task Loop (Autonomous execution)
    // Runs in 10ms increments as per safety-critical timing requirements.
    int cycles = 0;
    while(cycles < 5) { // Run a limited number of frames for the mock check
        if (Timer_Check_10ms_Tick()) {
            BrakeInput_t current_in = {0};
            BrakeOutput_t current_out = {0};

            // a. Read from CAN (BSW)
            CAN_Read_Brake_Pedal(&current_in);

            // b. Execute Application Logic (ASW: Unit Testable on PC)
            Brake_Control_Step(&current_in, &current_out);

            // c. Write to CAN / Actuators (BSW)
            CAN_Write_Status(&current_out);
            
            cycles++;
        }
    }
    
    printf("ECU operational check successfully shutdown.\n");
    return 0;
}
