#include <stdint.h>
#include <string.h>

#include "bcm_types.h"
#include "bcm_iface.h"

// Explicit prototype to fix implicit declaration error
void BCM_Safety_Check(const BcmInput_t *in, BcmOutput_t *out);

/* Register addresses for STM32F401RE */
#define RCC_BASE      0x40023800
#define RCC_AHB1ENR   (*(volatile uint32_t *)(RCC_BASE + 0x30))
#define RCC_APB1ENR   (*(volatile uint32_t *)(RCC_BASE + 0x40))

#define GPIOA_BASE    0x40020000
#define GPIOA_MODER   (*(volatile uint32_t *)(GPIOA_BASE + 0x00))
#define GPIOA_AFRL    (*(volatile uint32_t *)(GPIOA_BASE + 0x20))
#define GPIOA_ODR     (*(volatile uint32_t *)(GPIOA_BASE + 0x14))

#define GPIOC_BASE    0x40020800
#define GPIOC_MODER   (*(volatile uint32_t *)(GPIOC_BASE + 0x00))
#define GPIOC_IDR     (*(volatile uint32_t *)(GPIOC_BASE + 0x10))

#define USART2_BASE   0x40004400
#define USART2_SR     (*(volatile uint32_t *)(USART2_BASE + 0x00))
#define USART2_DR     (*(volatile uint32_t *)(USART2_BASE + 0x04))
#define USART2_BRR    (*(volatile uint32_t *)(USART2_BASE + 0x08))
#define USART2_CR1    (*(volatile uint32_t *)(USART2_BASE + 0x0C))

#define SCB_VTOR      (*(volatile uint32_t *)0xE000ED08)

/* Function Prototypes */
void main(void);
void Reset_Handler(void);
void uart_init(void);
void uart_write(int ch);
void uart_print(char *str);

/* Interrupt Vector Table (Starting at 0x08004000) */
__attribute__((section(".isr_vector")))
uint32_t *vector_table[] = {
    (uint32_t *)0x20018000, 
    (uint32_t *)Reset_Handler
};

void Reset_Handler(void) {
    main();
}

void delay(volatile uint32_t count) {
    while (count--) {
        __asm("nop");
    }
}

void uart_init(void) {
    RCC_AHB1ENR |= 0x01;  
    RCC_APB1ENR |= (1 << 17); 
    GPIOA_MODER &= ~((0x03 << 4) | (0x03 << 6));
    GPIOA_MODER |= ((0x02 << 4) | (0x02 << 6));
    GPIOA_AFRL &= ~((0x0F << 8) | (0x0F << 12));
    GPIOA_AFRL |= ((0x07 << 8) | (0x07 << 12));
    USART2_BRR = 0x068A; // 9600 baud
    USART2_CR1 = (1 << 13) | (1 << 3) | (1 << 2);
}

void uart_write(int ch) {
    while (!(USART2_SR & (1 << 7)))
    ;
    USART2_DR = (ch & 0xFF);
}

int uart_read(void) {
    if (USART2_SR & (1 << 5)) { // RXNE (Read data register not empty)
        return USART2_DR & 0xFF;
    }
    return -1;
}

void uart_print(char *str) {
    while (*str) {
        uart_write(*str++);
    }
}

void main(void) {
    /* 0. Enable FPU (Coprocessor 10 and 11) */
    /* This prevents a HardFault when using float variables */
    (*(volatile uint32_t *)(0xE000ED88)) |= ((3UL << 20) | (3UL << 22));

    // IMPORTANT: Make sure the CPU looks at OUR vector table
    SCB_VTOR = 0x08004000;

    uart_init();
    
    /* Configure PA5 (LED) as Output */
    RCC_AHB1ENR |= (1 << 0);
    GPIOA_MODER &= ~(0x03 << 10);
    GPIOA_MODER |= (0x01 << 10);

    /* Configure PC13 (Button) as Input */
    RCC_AHB1ENR |= (1 << 2);
    GPIOC_MODER &= ~(0x03 << 26);

    /* Initialize BCM structures */
    BcmInput_t bcm_in = {0};
    BcmOutput_t bcm_out = {0};
    
    bcm_in.brake_temp_celsius = 45.0f; // Nominal
    bcm_in.vehicle_speed = 60.0f;

    uart_print("\r\n=================================\r\n");
    uart_print("  BCM BRAKE CONTROLLER READY\r\n");
    uart_print("  VERSION: "); uart_print(BCM_SW_VERSION);
    uart_print("\r\n  TS:      "); uart_print(__DATE__); uart_print(" "); uart_print(__TIME__);
    uart_print("\r\n=================================\r\n");

    while (1) {
        /* A. Check for Remote Manipulation (HiL Interface) */
        int cmd = uart_read();
        if (cmd != -1) {
            if (cmd == 'P') { bcm_in.pedal_force = 100.0f; bcm_out.hydraulic_pressure = 10.0f; }
            if (cmd == 'p') { bcm_in.pedal_force = 0.0f; bcm_out.hydraulic_pressure = 0.0f; }
            if (cmd == 'T') { bcm_in.brake_temp_celsius = 250.0f; }
            if (cmd == 't') { bcm_in.brake_temp_celsius = 45.0f; }
            if (cmd == 'S') { bcm_in.vehicle_speed += 10.0f; }
            if (cmd == 's') { bcm_in.vehicle_speed = 0.0f; }
        }

        /* 1. Read Blue Button (Physical Fallback) */
        /* If button is pressed, it overrides remote 'p' */
        if (((GPIOC_IDR & (1 << 13)) == 0)) {
            bcm_in.pedal_force = 100.0f;
            bcm_out.hydraulic_pressure = 10.0f;
        }

        /* 3. Run Professional Safety Logic */
        BCM_Safety_Check(&bcm_in, &bcm_out);

        /* 4. Update Hardware LED based on Software Result */
        if (bcm_out.status_flag & 0x01) {
            GPIOA_ODR |= (1 << 5); // LED ON
        } else {
            GPIOA_ODR &= ~(1 << 5); // LED OFF
        }

        /* 5. Telemetry Logging */
        if (bcm_in.pedal_force > 0.1f) {
            uart_print("[BCM] Pedal: DEPRESSED | Lights: ACTIVE\r\n");
        } else {
            // Only print idle sporadically to avoid spamming
            static uint32_t idle_count = 0;
            if (++idle_count > 100) {
                uart_print("[BCM] Status: IDLE\r\n");
                idle_count = 0;
            }
        }

        delay(100000); // Small task delay
    }
}
