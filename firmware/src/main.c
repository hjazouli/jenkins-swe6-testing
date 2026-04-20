#include <stdint.h>
#include <string.h>
#include <stdio.h>

#include "bcm_iface.h"
#include "bcm_types.h"

// BCM interface includes all required module logic

/* Register addresses for STM32F401RE */
#define RCC_BASE 0x40023800
#define RCC_AHB1ENR (*(volatile uint32_t *)(RCC_BASE + 0x30))
#define RCC_APB1ENR (*(volatile uint32_t *)(RCC_BASE + 0x40))

#define GPIOA_BASE 0x40020000
#define GPIOA_MODER (*(volatile uint32_t *)(GPIOA_BASE + 0x00))
#define GPIOA_AFRL (*(volatile uint32_t *)(GPIOA_BASE + 0x20))
#define GPIOA_ODR (*(volatile uint32_t *)(GPIOA_BASE + 0x14))

#define GPIOC_BASE 0x40020800
#define GPIOC_MODER (*(volatile uint32_t *)(GPIOC_BASE + 0x00))
#define GPIOC_IDR (*(volatile uint32_t *)(GPIOC_BASE + 0x10))

#define USART2_BASE 0x40004400
#define USART2_SR (*(volatile uint32_t *)(USART2_BASE + 0x00))
#define USART2_DR (*(volatile uint32_t *)(USART2_BASE + 0x04))
#define USART2_BRR (*(volatile uint32_t *)(USART2_BASE + 0x08))
#define USART2_CR1 (*(volatile uint32_t *)(USART2_BASE + 0x0C))

#define SCB_VTOR (*(volatile uint32_t *)0xE000ED08)

/* Function Prototypes */
void main(void);
void Reset_Handler(void);
void uart_init(void);
void uart_write(int ch);
void uart_print(char *str);

/* Interrupt Vector Table (Starting at 0x08004000) */
__attribute__((section(".isr_vector")))
uint32_t *vector_table[] = {(uint32_t *)0x20018000, (uint32_t *)Reset_Handler};

void Reset_Handler(void) { main(); }

void delay(volatile uint32_t count) {
  while (count--) {
    __asm("nop");
  }
}

static uint32_t s_tick_count = 0;

void uart_init(void) {
  RCC_AHB1ENR |= 0x01;
  RCC_APB1ENR |= (1 << 17);
  GPIOA_MODER &= ~((0x03 << 4) | (0x03 << 6) | (0x03 << 10));
  GPIOA_MODER |= ((0x02 << 4) | (0x02 << 6) | (0x01 << 10));
  GPIOA_AFRL &= ~((0x0F << 8) | (0x0F << 12));
  GPIOA_AFRL |= ((0x07 << 8) | (0x07 << 12));
  USART2_BRR = 0x008B; // 115200 baud @ 16MHz HSI
  USART2_CR1 = (1 << 13) | (1 << 3) | (1 << 2);
}

void uart_write(int ch) {
  while (!(USART2_SR & (1 << 7)))
    ;
  USART2_DR = (ch & 0xFF);
}

int uart_read(void) {
  uint32_t sr = USART2_SR;
  if (sr & 0x08) { // ORE: Overrun Error
    (void)USART2_DR; // Dummy read to clear ORE
    return -1;
  }
  if (sr & (1 << 5)) { // RXNE (Read data register not empty)
    return USART2_DR & 0xFF;
  }
  return -1;
}

void command_handler(void); // Prototype for the new helper

void uart_print(char *str) {
  while (*str) {
    uart_write(*str++);
    // Check for incoming data between EVERY transmitted byte to prevent ORE
    command_handler();
  }
}

void print_int(int val) {
  char buf[16];
  int i = 0;
  if (val == 0) {
    uart_write('0');
    return;
  }
  if (val < 0) {
    uart_write('-');
    val = -val;
  }
  while (val > 0 && i < 15) {
    buf[i++] = (val % 10) + '0';
    val /= 10;
  }
  while (i > 0) {
    uart_write(buf[--i]);
  }
}

/* Simple parser to convert "123.4" strings to float */
float parse_float(char *s) {
  float res = 0.0, fact = 1.0;
  int point_seen = 0;
  if (*s == '-') {
    s++;
    fact = -1.0;
  }
  for (; *s; s++) {
    if (*s == '.') {
      point_seen = 1;
      continue;
    }
    int d = *s - '0';
    if (d >= 0 && d <= 9) {
      if (point_seen)
        fact /= 10.0f;
      res = res * 10.0f + (float)d;
    }
  }
  return res * fact;
}

char cmd_buffer[32];
int cmd_idx = 0;

/* Global state for BCM */
BcmInput_t bcm_in = {0};
BcmOutput_t bcm_out = {0};

void command_handler(void) {
  static int s_lock = 0;
  if (s_lock) return; // Prevent re-entrancy during uart_print recursion
  s_lock = 1;

  int rx_byte;
  while ((rx_byte = uart_read()) != -1) {
    if (rx_byte == '\n' || rx_byte == '\r') {
      cmd_buffer[cmd_idx] = '\0';
      if (cmd_idx >= 1) {
        char type = cmd_buffer[0];
        float val = parse_float(&cmd_buffer[1]);
        if (type == 'P') bcm_in.pedal_force = val;
        if (type == 'T') bcm_in.brake_temp_celsius = val;
        if (type == 'S') bcm_in.vehicle_speed = val;
        if (type == 'R') {
          /* Total System Reset */
          memset(&bcm_in, 0, sizeof(bcm_in));
          memset(&bcm_out, 0, sizeof(bcm_out));
          BCM_Init(&bcm_out); // Re-initialize default output states
          uart_print("[SYS] RESET PERFORMED\r\n");
        }
        if (type == 'V') {
          uart_print("[VER] ");
          uart_print(BCM_SW_VERSION);
          uart_print("\r\n");
        }
        uart_print("[ACK] RECEIVED\r\n");
      }
      cmd_idx = 0;
    } else if (cmd_idx < 31) {
      cmd_buffer[cmd_idx++] = (char)rx_byte;
    }
  }
  s_lock = 0;
}

void main(void) {
  /* 0. Enable FPU (Coprocessor 10 and 11) */
  /* This prevents a HardFault when using float variables */
  (*(volatile uint32_t *)(0xE000ED88)) |= ((3UL << 20) | (3UL << 22));

  // IMPORTANT: Make sure the CPU looks at OUR vector table
  SCB_VTOR = 0x08004000;

  /* 1. Hardware Initialization */
  uart_init();

  /* Configure PC13 (Button) as Input for future functional growth */
  RCC_AHB1ENR |= (1 << 2);
  GPIOC_MODER &= ~(0x03 << 26);

  /* Initialize BCM structures */
  bcm_in.brake_temp_celsius = 45.0f; // Nominal
  bcm_in.vehicle_speed = 60.0f;

  uart_print("\r\n--- BCM BOOTED ---\r\n");
  uart_print("  VERSION: ");
  uart_print(BCM_SW_VERSION);
  uart_print("\r\n=================================\r\n");

  while (1)
  {
    /* A. Check for Remote Manipulation (HiL Interface) */
    command_handler();

    /* B. Execution of BCM Logic Sequencer */
    BCM_Step(&bcm_in, &bcm_out);

    /* C. Periodic Telemetry (Throttle to ~10Hz) */
    if (s_tick_count % 100 == 0)
    {
      uart_print("[BCM-V101] P:");
      print_int((int)bcm_in.pedal_force);
      uart_print(" S:");
      print_int((int)bcm_in.vehicle_speed);
      uart_print(" F:");
      print_int((int)bcm_out.front_hydraulic_pressure);
      uart_print(" R:");
      print_int((int)bcm_out.rear_hydraulic_pressure);
      uart_print(" Lights:");
      uart_print((bcm_out.status_flag & 0x01) ? "ACTIVE" : "OFF");
      uart_print(" FLAG:");
      print_int((int)bcm_out.status_flag);
      uart_print("\r\n");
    }

    /* D. Heartbeat LED Toggle (Visual Life Proof) */
    static uint32_t heartbeat_cnt = 0;
    if (++heartbeat_cnt > 100)
    {
      GPIOA_ODR ^= (1 << 5); 
      heartbeat_cnt = 0;
    }

    delay(1000); 
    s_tick_count++;
  }
}
