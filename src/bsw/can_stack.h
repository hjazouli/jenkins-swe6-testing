#ifndef CAN_STACK_H
#define CAN_STACK_H

#include "../app/brake_logic.h"

/**
 * Basic Software (BSW): Generic CAN Stack abstraction
 */
void CAN_Init(void);
void CAN_Read_Brake_Pedal(BrakeInput_t* input);
void CAN_Write_Status(const BrakeOutput_t* output);

#endif /* CAN_STACK_H */
