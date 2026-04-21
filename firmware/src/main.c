#include "bcm_iface.h"
#include "bcm_types.h"
#include <stdint.h>

/* STM32 Low-Layer Drivers */
#include "stm32f4xx_ll_bus.h"
#include "stm32f4xx_ll_rcc.h"
#include "stm32f4xx_ll_system.h"
#include "stm32f4xx_ll_usart.h"
#include "stm32f4xx_ll_utils.h"

/* Note: stm32f4xx_ll_gpio.h is missing in this project, 
   falling back to CMSIS device header access for GPIO. */
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

  /* Configure PA2 (TX) and PA3 (RX) as AF7 (USART2) 
     Falling back to CMSIS access as LL GPIO header is missing */
  GPIOA->MODER &= ~(GPIO_MODER_MODER2_Msk | GPIO_MODER_MODER3_Msk);
  GPIOA->MODER |= (0x02 << GPIO_MODER_MODER2_Pos) | (0x02 << GPIO_MODER_MODER3_Pos);
  
  GPIOA->AFR[0] &= ~(GPIO_AFRL_AFSEL2_Msk | GPIO_AFRL_AFSEL3_Msk);
  GPIOA->AFR[0] |= (0x07 << GPIO_AFRL_AFSEL2_Pos) | (0x07 << GPIO_AFRL_AFSEL3_Pos);

  GPIOA->OSPEEDR |= (0x03 << GPIO_OSPEEDR_OSPEED2_Pos) | (0x03 << GPIO_OSPEEDR_OSPEED3_Pos);

  /* Configure PA5 (LED) as Output */
  GPIOA->MODER &= ~GPIO_MODER_MODER5_Msk;
  GPIOA->MODER |= (0x01 << GPIO_MODER_MODER5_Pos);

  /* Configure UART Parameters using inline functions to avoid linker errors 
     (as .c implementations of Init functions are missing) */
  LL_USART_SetBaudRate(USART2, 16000000, LL_USART_OVERSAMPLING_16, 9600);
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
  if (LL_USART_IsActiveFlag_ORE(USART2)) {
    (void)LL_USART_ReceiveData8(USART2); /* Clear ORE by reading DR */
    return -1;
  }
  if (LL_USART_IsActiveFlag_RXNE(USART2)) {
    return LL_USART_ReceiveData8(USART2);
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
  /* This uses CMSIS Core functions */
  SysTick_Config(160000); 

  /* Hardware Monitoring / Button Setup (PC13) */
  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOC);
  GPIOC->MODER &= ~GPIO_MODER_MODER13_Msk; /* Input Mode */

  memset(&bcm_in, 0, sizeof(bcm_in));
  memset(&bcm_out, 0, sizeof(bcm_out));
  bcm_in.brake_temp_celsius = 45.0f;
  bcm_in.vehicle_speed = 60.0f;

  uart_print("\r\n--- BCM LL/CMSIS ONLINE ---\r\n");

  while (1) {
    /* Fastest Polling for Command Listener */
    command_handler();

    /* B. Check for SysTick (Deterministic 100Hz Heartbeat) */
    if (SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk) {
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
        GPIOA->ODR ^= GPIO_ODR_OD5;
      }
    }

    /* Raw Loop Pulse (Verify UART life if SysTick is stalled) */
    if (s_loop_cnt % 1000000 == 0) {
      uart_print(" [RAW] LOOP ALIVE\r\n");
    }

    s_loop_cnt++;
  }
}
