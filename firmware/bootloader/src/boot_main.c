#include <stdint.h>

#define APP_START_ADDRESS 0x08004000

/* Register addresses */
#define RCC_AHB1ENR   (*(volatile uint32_t *)0x40023830)
#define GPIOC_MODER   (*(volatile uint32_t *)0x40020800)
#define GPIOC_IDR     (*(volatile uint32_t *)0x40020810)

#define GPIOA_MODER   (*(volatile uint32_t *)0x40020000)
#define GPIOA_ODR     (*(volatile uint32_t *)0x40020014)

#define SCB_VTOR      (*(volatile uint32_t *)0xE000ED08)

/* Function prototypes */
void main(void);
void Reset_Handler(void);
void jump_to_app(void);

/* Interrupt Vector Table */
__attribute__((section(".isr_vector")))
uint32_t *vector_table[] = {
    (uint32_t *)0x20018000,
    (uint32_t *)Reset_Handler
};

void Reset_Handler(void) {
    main();
}

/**
 * @brief The Jump Function (The "Pro" Logic)
 */
void jump_to_app(void) {
    // 1. Get the Application's Initial Stack Pointer
    uint32_t app_sp = *(volatile uint32_t *)APP_START_ADDRESS;
    
    // 2. Get the Application's Reset Handler
    uint32_t app_reset_handler_addr = *(volatile uint32_t *)(APP_START_ADDRESS + 4);
    void (*app_reset_handler)(void) = (void (*)(void))app_reset_handler_addr;

    // 3. Set the Vector Table Offset Register (VTOR)
    SCB_VTOR = APP_START_ADDRESS;

    // 4. Set the Main Stack Pointer (MSP) using Assembly
    __asm volatile ("msr msp, %0" : : "r" (app_sp) : );

    // 5. Jump to Application!
    app_reset_handler();
}

void main(void) {
    /* 1. Enable Clock for GPIOA (LED) and GPIOC (Button) */
    RCC_AHB1ENR |= (1 << 0) | (1 << 2);

    /* 2. Configure PC13 (Button) as Input */
    GPIOC_MODER &= ~(0x03 << 26);

    /* 3. Configure PA5 (LED) as Output */
    GPIOA_MODER &= ~(0x03 << 10);
    GPIOA_MODER |= (0x01 << 10);

    /* 4. Check for "Update Mode" (Blue Button pressed = LOW) */
    if ( (GPIOC_IDR & (1 << 13)) == 0 ) {
        /* STAY IN BOOTLOADER (Monitor Mode) */
        // Turn LED ON solid to show we are in Bootloader mode
        GPIOA_ODR |= (1 << 5);
        while(1); // Real bootloader would wait for UART here
    } else {
        /* JUMP TO APPLICATION */
        jump_to_app();
    }
}
