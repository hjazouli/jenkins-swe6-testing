#include "bcm_iface.h"
#include "bcm_types.h"
#include <stdint.h>

/* STM32 Low-Layer Drivers */
#include "stm32f4xx_ll_bus.h"
#include "stm32f4xx_ll_rcc.h"
#include "stm32f4xx_ll_system.h"
#include "stm32f4xx_ll_usart.h"
#include "stm32f4xx_ll_utils.h"

#include "stm32f4xx_ll_gpio.h"
#include "stm32f401xe.h" 

/* Bare-metal memset replacement */
void *memset(void *s, int c, uint32_t n) {
  uint8_t *p = (uint8_t *)s;
  while (n--)
    *p++ = (uint8_t)c;
  return s;
}

/* BCM interface includes all required modules logic */
void main(void);
void uart_init(void);
void uart_write(int ch);
void uart_print(char *str);
void command_handler(void);

void delay(volatile uint32_t count) {
  while (count--) {
    __asm("nop");
  }
}

static uint32_t s_tick_count = 0;
static uint32_t s_loop_cnt = 0;

void uart_init(void) {
  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOA);
  LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_USART2);

  /* Configure PA2 (TX) and PA3 (RX) using Official LL Drivers */
  LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_2, LL_GPIO_MODE_ALTERNATE);
  LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_3, LL_GPIO_MODE_ALTERNATE);
  
  LL_GPIO_SetAFPin_0_7(GPIOA, LL_GPIO_PIN_2, LL_GPIO_AF_7);
  LL_GPIO_SetAFPin_0_7(GPIOA, LL_GPIO_PIN_3, LL_GPIO_AF_7);

  LL_GPIO_SetPinSpeed(GPIOA, LL_GPIO_PIN_2, LL_GPIO_SPEED_FREQ_VERY_HIGH);
  LL_GPIO_SetPinSpeed(GPIOA, LL_GPIO_PIN_3, LL_GPIO_SPEED_FREQ_VERY_HIGH);

  /* Configure PA5 (LED) as Output */
  LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_5, LL_GPIO_MODE_OUTPUT);

  /* Configure UART Parameters using Official LL-Style Logic.
     Manual BRR used to avoid 64-bit math dependency in nostdlib.
     Calculation: (16MHz + 4800) / 9600 = 1667 (0x683) */
  USART2->BRR = 0x683;
  LL_USART_SetDataWidth(USART2, LL_USART_DATAWIDTH_8B);
  LL_USART_SetStopBitsLength(USART2, LL_USART_STOPBITS_1);
  LL_USART_SetParity(USART2, LL_USART_PARITY_NONE);
  LL_USART_SetTransferDirection(USART2, LL_USART_DIRECTION_TX_RX);
  LL_USART_SetOverSampling(USART2, LL_USART_OVERSAMPLING_16);
  
  LL_USART_Enable(USART2);
}

void uart_write(int c) {
  while (!LL_USART_IsActiveFlag_TXE(USART2)) {
    command_handler();
  }
  LL_USART_TransmitData8(USART2, (uint8_t)c);
}

int uart_read(void) {
  /* Clear any pending errors to ensure RX path is open */
  if (USART2->SR & (USART_SR_ORE | USART_SR_NE | USART_SR_FE)) {
    (void)USART2->SR;
    (void)USART2->DR;
  }
  
  if (LL_USART_IsActiveFlag_RXNE(USART2)) {
    return (int)LL_USART_ReceiveData8(USART2);
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
  int rx_byte;
  while ((rx_byte = uart_read()) != -1) {
    /* DEBUG: Toggle LED on any RX byte using LL Driver */
    LL_GPIO_TogglePin(GPIOA, LL_GPIO_PIN_5);

    if (rx_byte == '\n' || rx_byte == '\r') {
      if (cmd_idx >= 1) {
        cmd_buffer[cmd_idx] = '\0';
        char type = cmd_buffer[0];
        float val = parse_float(&cmd_buffer[1]);

        if (type == 'P')
          bcm_in.pedal_force = val;
        else if (type == 'T')
          bcm_in.brake_temp_celsius = val;
        else if (type == 'S')
          bcm_in.vehicle_speed = val;
        else if (type == 'R') {
          memset(&bcm_in, 0, sizeof(bcm_in));
          memset(&bcm_out, 0, sizeof(bcm_out));
          BCM_Init(&bcm_out);
          uart_print("[SYS] RESET PERFORMED\r\n");
        } else {
          uart_print("[ACK] RECEIVED\r\n");
        }
        cmd_idx = 0;
      }
    } else if (cmd_idx < 30) {
      cmd_buffer[cmd_idx++] = (char)rx_byte;
    }
  }
}

#define SYSTICK_BASE 0xE000E010
#define SYSTICK_CTRL (*(volatile uint32_t *)(SYSTICK_BASE + 0x00))
#define SYSTICK_LOAD (*(volatile uint32_t *)(SYSTICK_BASE + 0x04))
#define SYSTICK_VAL (*(volatile uint32_t *)(SYSTICK_BASE + 0x08))

void main(void) {
  /* 1. Hardware Initialization */
  uart_init();

  /* 2. SysTick Configuration: 10ms interval @ 16MHz HSI */
  /* This uses CMSIS Core functions. Disable interrupt for polling mode. */
  SysTick_Config(160000); 
  SysTick->CTRL &= ~SysTick_CTRL_TICKINT_Msk;

  /* Hardware Monitoring / Button Setup (PC13) */
  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOC);
  LL_GPIO_SetPinMode(GPIOC, LL_GPIO_PIN_13, LL_GPIO_MODE_INPUT); 

  memset(&bcm_in, 0, sizeof(bcm_in));
  memset(&bcm_out, 0, sizeof(bcm_out));
  bcm_in.brake_temp_celsius = 45.0f;
  bcm_in.vehicle_speed = 60.0f;

  uart_print("\r\n--- BCM SYSTICK ONLINE ---\r\n");

  while (1) {
    /* Fastest Polling for Command Listener */
    command_handler();

    /* Check for SysTick (Deterministic 100Hz Heartbeat) */
    if (SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk) {
      /* This bit is set every 10ms */
      BCM_Step(&bcm_in, &bcm_out);
      s_tick_count++;

      /* Send Telemetry at 1Hz (Every 100 ticks) */
      if (s_tick_count % 100 == 0) {
        int speed = (int)bcm_in.vehicle_speed;
        int pedal = (int)bcm_in.pedal_force;
        int f_press = (int)bcm_out.front_hydraulic_pressure;
        int r_press = (int)bcm_out.rear_hydraulic_pressure;
        volatile int is_act = bcm_out.brake_light;
        char *light_status = is_act ? "ACTIVE" : "OFF";
        
        uart_print("[BCM-V101] T:");
        print_int(s_tick_count);
        uart_print(" P:");
        print_int(pedal);
        uart_print(" S:");
        print_int(speed);
        uart_print(" F:");
        print_int(f_press);
        uart_print(" R:");
        print_int(r_press);
        uart_print(" Lights:");
        uart_print(light_status);
        uart_print(" FLAG:");
        print_int(bcm_out.flags);
        uart_print("\r\n");
      }

      /* CPU Heartbeat (PA5) toggle every 0.5s */
      if (s_tick_count % 50 == 0) {
        GPIOA->ODR ^= (1 << 5); // Toggle PA5
      }
    }
  }
}

