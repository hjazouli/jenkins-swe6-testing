#ifndef SCHM_H
#define SCHM_H

#include <stdint.h>

/**
 * Schedule Manager (BSW): The "Heartbeat" of the OS
 */
void Timer_10ms_Start(void);
uint8_t Timer_Check_10ms_Tick(void);

#endif /* SCHM_H */
