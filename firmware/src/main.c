#include "bcm_iface.h"
#include "bcm_types.h"
#include <stdint.h>

/* Bare-metal memset replacement */
void *memset(void *s, int c, uint32_t n) {
  uint8_t *p = (uint8_t *)s;
  while (n--)
    *p++ = (uint8_t)c;
  return s;
}

/* BCM interface includes all required modules logic */

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
void uart_init(void);
void uart_write(int ch);
void uart_print(char *str);

void delay(volatile uint32_t count) {
  while (count--) {
    __asm("nop");
  }
}

static uint32_t s_tick_count = 0;
static uint32_t s_loop_cnt = 0;

void uart_init(void) {
  RCC_AHB1ENR |= 0x01;
  RCC_APB1ENR |= (1 << 17);
  GPIOA_MODER &= ~((0x03 << 4) | (0x03 << 6) | (0x03 << 10));
  GPIOA_MODER |= ((0x02 << 4) | (0x02 << 6) | (0x01 << 10));
  GPIOA_AFRL &= ~((0x0F << 8) | (0x0F << 12));
  GPIOA_AFRL |= ((0x07 << 8) | (0x07 << 12));
  /* Baud Rate: 9600 @ 16MHz */
  USART2_BRR = (104 << 4) | 3; // 0x683
  USART2_CR1 = (1 << 13) | (1 << 3) | (1 << 2);
}

void command_handler(void);

void uart_write(int c) {
  while (!(USART2_SR & 0x80)) {
    // While waiting for the transmitter to be ready, check for incoming
    // commands!
    command_handler();
  }
  USART2_DR = (c & 0xFF);
}

int uart_read(void) {
  uint32_t sr = USART2_SR;
  if (sr & 0x08) {   // ORE: Overrun Error
    (void)USART2_DR; // Dummy read to clear ORE
    return -1;
  }
  if (sr & (1 << 5)) { // RXNE (Read data register not empty)
    return USART2_DR & 0xFF;
  }
  return -1;
}

void uart_print(char *str) {
  while (*str) {
    uart_write(*str++);
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

static char s_rsp[64] = {0};

void command_handler(void) {
  static int s_lock = 0;
  if (s_lock)
    return;
  s_lock = 1;

  int rx_byte;
  while ((rx_byte = uart_read()) != -1) {
    if (rx_byte == '\n' || rx_byte == '\r') {
      cmd_buffer[cmd_idx] = '\0';
      if (cmd_idx >= 1) {
        char type = cmd_buffer[0];
        float val = parse_float(&cmd_buffer[1]);
        if (type == 'P')
          bcm_in.pedal_force = val;
        if (type == 'T')
          bcm_in.brake_temp_celsius = val;
        if (type == 'S')
          bcm_in.vehicle_speed = val;
        if (type == 'R') {
          memset(&bcm_in, 0, sizeof(bcm_in));
          memset(&bcm_out, 0, sizeof(bcm_out));
          BCM_Init(&bcm_out);
          /* Match Python expected string: [SYS] RESET PERFORMED */
          char *msg = "[SYS] RESET PERFORMED\r\n";
          for (int i = 0; msg[i] && i < 60; i++)
            s_rsp[i] = msg[i];
        } else {
          /* Match Python expected string: [ACK] RECEIVED */
          char *msg = "[ACK] RECEIVED\r\n";
          for (int i = 0; msg[i] && i < 60; i++)
            s_rsp[i] = msg[i];
        }
      }
      cmd_idx = 0;
    } else if (cmd_idx < 31) {
      cmd_buffer[cmd_idx++] = (char)rx_byte;
    }
  }
  s_lock = 0;
}

#define SYSTICK_BASE 0xE000E010
#define SYSTICK_CTRL (*(volatile uint32_t *)(SYSTICK_BASE + 0x00))
#define SYSTICK_LOAD (*(volatile uint32_t *)(SYSTICK_BASE + 0x04))
#define SYSTICK_VAL (*(volatile uint32_t *)(SYSTICK_BASE + 0x08))

void main(void) {
  /* 1. Hardware Initialization */
  uart_init();

  /* 2. SysTick Configuration: 10ms interval @ 16MHz HSI */
  /* 160,000 cycles = 10ms. (16,000,000 / 100) */
  SYSTICK_LOAD = 160000 - 1;
  SYSTICK_VAL = 0;
  SYSTICK_CTRL = 0x05; // Clock source = CPU, Enable = 1

  /* Hardware Monitoring / Button Setup */
  RCC_AHB1ENR |= (1 << 2);
  GPIOC_MODER &= ~(0x03 << 26);

  memset(&bcm_in, 0, sizeof(bcm_in));
  memset(&bcm_out, 0, sizeof(bcm_out));
  bcm_in.brake_temp_celsius = 45.0f;
  bcm_in.vehicle_speed = 60.0f;

  uart_print("\r\n--- BCM SYSTICK ONLINE ---\r\n");

  while (1) {
    /* Fastest Polling for Command Listener */
    command_handler();

    /* B. Check for SysTick (Deterministic 100Hz Heartbeat) */
    if (SYSTICK_CTRL & (1 << 16)) {
      /* This bit is set every 10ms */
      BCM_Step(&bcm_in, &bcm_out);
      s_tick_count++;

      /* C. Handle Responses in Sync with Logic */
      if (s_rsp[0] != '\0') {
        uart_print(s_rsp);
        memset(s_rsp, 0, sizeof(s_rsp));
      }

      /* D. Telemetry Report (Every 100 Logic Ticks = 1Hz) */
      if (s_tick_count % 100 == 0) {
        uart_print("[BCM-V101] T:");
        print_int((int)s_tick_count);
        uart_print(" P:");
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

      /* CPU Heartbeat (PA5) toggle every 0.5s */
      if (s_tick_count % 50 == 0) {
        GPIOA_ODR ^= (1 << 5);
      }
    }

    /* Raw Loop Pulse (Verify UART life if SysTick is stalled) */
    if (s_loop_cnt % 1000000 == 0) {
      uart_print(" [RAW] LOOP ALIVE\r\n");
    }

    s_loop_cnt++;
  }
}
