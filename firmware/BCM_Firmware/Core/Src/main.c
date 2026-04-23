/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * @file           : main.c
 * @brief          : Main program body
 ******************************************************************************
 * @attention
 *
 * Copyright (c) 2026 STMicroelectronics.
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 * If no LICENSE file comes with this software, it is provided AS-IS.
 *
 ******************************************************************************
 */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
#include "bcm_iface.h"
#include "bcm_types.h"
#include <stdio.h>
#include <string.h>


/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
static uint32_t s_tick_count = 0;
BcmInput_t bcm_in = {0};
BcmOutput_t bcm_out = {0};
char cmd_buffer[32];
int cmd_idx = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
/* USER CODE BEGIN PFP */
void uart_write(int ch);
void uart_print(char *str);
void print_int(int val);
void BCM_Periodic_Task(void);
void BCM_UART_RX_Callback(uint8_t byte);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
int uart_read(void) {
  /* Use direct register check as fallback for robustness in polling */
  if (USART2->SR & (USART_SR_ORE | USART_SR_NE | USART_SR_FE)) {
    (void)USART2->SR;
    (void)USART2->DR;
  }
  if (LL_USART_IsActiveFlag_RXNE(USART2)) {
    return (int)LL_USART_ReceiveData8(USART2);
  }
  return -1;
}

void uart_write(int c) {
  /* No need to poll command_handler here; interrupts handle RX asynchronously
   */
  while (!LL_USART_IsActiveFlag_TXE(USART2)) {
  }
  LL_USART_TransmitData8(USART2, (uint8_t)c);
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

void BCM_UART_RX_Callback(uint8_t rx_byte) {
  /* This is called by USART2_IRQHandler */
  if (rx_byte == '\n' || rx_byte == '\r') {
    if (cmd_idx >= 1) {
      cmd_buffer[cmd_idx] = '\0';
      char type = cmd_buffer[0];
      float val = parse_float(&cmd_buffer[1]);

      if (type == 'P') {
        if (val > 100.0f)
          val = 100.0f;
        if (val < 0.0f)
          val = 0.0f;
        bcm_in.pedal_force = val;
        uart_print("[ACK] RECEIVED\r\n");
      } else if (type == 'T') {
        bcm_in.brake_temp_celsius = val;
        uart_print("[ACK] RECEIVED\r\n");
      } else if (type == 'S') {
        bcm_in.vehicle_speed = val;
        uart_print("[ACK] RECEIVED\r\n");
      } else if (type == 'R') {
        memset(&bcm_in, 0, sizeof(bcm_in));
        memset(&bcm_out, 0, sizeof(bcm_out));
        BCM_Init(&bcm_out);
        uart_print("[SYS] RESET PERFORMED\r\n");
      } else if (type == 'W') {
        bcm_in.brake_wear_pct = val;
        uart_print("[ACK] RECEIVED\r\n");
      } else {
        uart_print("[ACK] RECEIVED\r\n");
      }
      cmd_idx = 0;
    }
  } else if (cmd_idx < 30) {
    cmd_buffer[cmd_idx++] = (char)rx_byte;
  }
}

void BCM_Periodic_Task(void) {
  /* This is called by SysTick_Handler every 1ms */
  s_tick_count++;

  /* Run BCM Logic Step @ 100Hz (every 10ms) */
  if (s_tick_count % 10 == 0) {
    BCM_Step(&bcm_in, &bcm_out);

    /* Telemetry Report @ 1Hz */
    if (s_tick_count % 1000 == 0) {
      uart_print("[BCM-V101] T:");
      print_int((int)s_tick_count);
      uart_print(" P:");
      print_int((int)bcm_in.pedal_force);
      uart_print(" S:");
      print_int((int)bcm_in.vehicle_speed);
      uart_print(" W:");
      print_int((int)bcm_in.brake_wear_pct);
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

    /* CPU Heartbeat LED toggle every 0.5s */
    if (s_tick_count % 500 == 0) {
      LL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);
    }
  }
}
/* USER CODE END 0 */

/**
 * @brief  The application entry point.
 * @retval int
 */
int main(void) {

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick.
   */
  LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_SYSCFG);
  LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_PWR);

  /* System interrupt init*/
  NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4);

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  /* USER CODE BEGIN 2 */
  LL_GPIO_SetPinMode(LD2_GPIO_Port, LD2_Pin, LL_GPIO_MODE_OUTPUT);
  LL_GPIO_SetOutputPin(LD2_GPIO_Port, LD2_Pin);

  uart_print("\r\n--- BCM BOOTING ---\r\n");

  BCM_Init(&bcm_out);
  bcm_in.brake_temp_celsius = 45.0f;
  bcm_in.vehicle_speed = 60.0f;

  SysTick->CTRL |= (SysTick_CTRL_TICKINT_Msk | SysTick_CTRL_ENABLE_Msk |
                    SysTick_CTRL_CLKSOURCE_Msk);

  LL_USART_EnableIT_RXNE(USART2);
  NVIC_SetPriority(USART2_IRQn,
                   NVIC_EncodePriority(NVIC_GetPriorityGrouping(), 5, 0));
  NVIC_EnableIRQ(USART2_IRQn);

  uart_print("\r\n--- BCM INTERRUPT ARCH ONLINE ---\r\n");
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1) {
    /* CPU idles here. All logic is in Interrupt Service Routines (ISRs) */
    __WFI(); /* Wait For Interrupt: Saves power until the next SysTick or UART
                byte */
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
 * @brief System Clock Configuration
 * @retval None
 */
void SystemClock_Config(void) {
  LL_FLASH_SetLatency(LL_FLASH_LATENCY_2);
  while (LL_FLASH_GetLatency() != LL_FLASH_LATENCY_2) {
  }
  LL_PWR_SetRegulVoltageScaling(LL_PWR_REGU_VOLTAGE_SCALE2);
  LL_RCC_HSI_SetCalibTrimming(16);
  LL_RCC_HSI_Enable();

  /* Wait till HSI is ready */
  while (LL_RCC_HSI_IsReady() != 1) {
  }
  LL_RCC_PLL_ConfigDomain_SYS(LL_RCC_PLLSOURCE_HSI, LL_RCC_PLLM_DIV_16, 336,
                              LL_RCC_PLLP_DIV_4);
  LL_RCC_PLL_Enable();

  /* Wait till PLL is ready */
  while (LL_RCC_PLL_IsReady() != 1) {
  }
  while (LL_PWR_IsActiveFlag_VOS() == 0) {
  }
  LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);
  LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_2);
  LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);
  LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_PLL);

  /* Wait till System clock is ready */
  while (LL_RCC_GetSysClkSource() != LL_RCC_SYS_CLKSOURCE_STATUS_PLL) {
  }
  LL_Init1msTick(84000000);
  LL_SetSystemCoreClock(84000000);
  LL_RCC_SetTIMPrescaler(LL_RCC_TIM_PRESCALER_TWICE);
}

/**
 * @brief USART2 Initialization Function
 * @param None
 * @retval None
 */
static void MX_USART2_UART_Init(void) {

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  LL_USART_InitTypeDef USART_InitStruct = {0};

  LL_GPIO_InitTypeDef GPIO_InitStruct = {0};

  /* Peripheral clock enable */
  LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_USART2);

  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOA);
  /**USART2 GPIO Configuration
  PA2   ------> USART2_TX
  PA3   ------> USART2_RX
  */
  GPIO_InitStruct.Pin = USART_TX_Pin | USART_RX_Pin;
  GPIO_InitStruct.Mode = LL_GPIO_MODE_ALTERNATE;
  GPIO_InitStruct.Speed = LL_GPIO_SPEED_FREQ_LOW;
  GPIO_InitStruct.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
  GPIO_InitStruct.Pull = LL_GPIO_PULL_NO;
  GPIO_InitStruct.Alternate = LL_GPIO_AF_7;
  LL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  USART_InitStruct.BaudRate = 115200;
  USART_InitStruct.DataWidth = LL_USART_DATAWIDTH_8B;
  USART_InitStruct.StopBits = LL_USART_STOPBITS_1;
  USART_InitStruct.Parity = LL_USART_PARITY_NONE;
  USART_InitStruct.TransferDirection = LL_USART_DIRECTION_TX_RX;
  USART_InitStruct.HardwareFlowControl = LL_USART_HWCONTROL_NONE;
  USART_InitStruct.OverSampling = LL_USART_OVERSAMPLING_16;
  LL_USART_Init(USART2, &USART_InitStruct);
  LL_USART_ConfigAsyncMode(USART2);
  LL_USART_Enable(USART2);
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */
}

/**
 * @brief GPIO Initialization Function
 * @param None
 * @retval None
 */
static void MX_GPIO_Init(void) {
  LL_EXTI_InitTypeDef EXTI_InitStruct = {0};
  LL_GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOC);
  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOH);
  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOA);
  LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOB);

  /**/
  LL_GPIO_ResetOutputPin(LD2_GPIO_Port, LD2_Pin);

  /**/
  LL_SYSCFG_SetEXTISource(LL_SYSCFG_EXTI_PORTC, LL_SYSCFG_EXTI_LINE13);

  /**/
  EXTI_InitStruct.Line_0_31 = LL_EXTI_LINE_13;
  EXTI_InitStruct.LineCommand = ENABLE;
  EXTI_InitStruct.Mode = LL_EXTI_MODE_IT;
  EXTI_InitStruct.Trigger = LL_EXTI_TRIGGER_FALLING;
  LL_EXTI_Init(&EXTI_InitStruct);

  /**/
  LL_GPIO_SetPinPull(B1_GPIO_Port, B1_Pin, LL_GPIO_PULL_NO);

  /**/
  LL_GPIO_SetPinMode(B1_GPIO_Port, B1_Pin, LL_GPIO_MODE_INPUT);

  /**/
  GPIO_InitStruct.Pin = LD2_Pin;
  GPIO_InitStruct.Mode = LL_GPIO_MODE_OUTPUT;
  GPIO_InitStruct.Speed = LL_GPIO_SPEED_FREQ_LOW;
  GPIO_InitStruct.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
  GPIO_InitStruct.Pull = LL_GPIO_PULL_NO;
  LL_GPIO_Init(LD2_GPIO_Port, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
 * @brief  This function is executed in case of error occurrence.
 * @retval None
 */
void Error_Handler(void) {
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1) {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
 * @brief  Reports the name of the source file and the source line number
 *         where the assert_param error has occurred.
 * @param  file: pointer to the source file name
 * @param  line: assert_param error line source number
 * @retval None
 */
void assert_failed(uint8_t *file, uint32_t line) {
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line
     number, ex: printf("Wrong parameters value: file %s on line %d\r\n", file,
     line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
