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
typedef enum {
  FRAME_WAIT_START,
  FRAME_WAIT_TYPE,
  FRAME_WAIT_LEN,
  FRAME_WAIT_PAYLOAD,
  FRAME_WAIT_CRC1,
  FRAME_WAIT_CRC2
} FrameState_t;

/* Binary telemetry payload sent with every RESP_TELEMETRY frame. Packed so
 * its wire layout matches Python's struct.unpack("<IfffffBi", ...) exactly. */
typedef struct __attribute__((packed)) {
  uint32_t tick;
  float pedal;
  float speed;
  float wear;
  float front;
  float rear;
  uint8_t status_flag;
  int32_t chip_temp_c;
} TelemetryPayload_t;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define FRAME_START_BYTE 0x7E
#define FRAME_MAX_PAYLOAD 32

#define CMD_SET_PEDAL 0x01
#define CMD_SET_SPEED 0x02
#define CMD_SET_TEMP  0x03
#define CMD_RESET     0x04
#define CMD_SET_WEAR  0x05

#define RESP_ACK       0x10
#define RESP_NACK      0x11
#define RESP_TELEMETRY 0x20
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
volatile uint32_t s_tick_count = 0;
volatile uint8_t g_telem_pending = 0;
BcmInput_t bcm_in = {0};
BcmOutput_t bcm_out = {0};

/* Binary frame protocol state (see BCM_UART_RX_Callback) */
static FrameState_t s_frame_state = FRAME_WAIT_START;
static uint8_t s_frame_type = 0;
static uint8_t s_frame_len = 0;
static uint8_t s_frame_payload[FRAME_MAX_PAYLOAD];
static uint8_t s_frame_payload_idx = 0;
static uint16_t s_frame_crc_recv = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_ADC1_Init(void);
/* USER CODE BEGIN PFP */
void uart_write(int ch);
void uart_print(char *str);
void BCM_Periodic_Task(void);
void BCM_UART_RX_Callback(uint8_t byte);
int32_t BCM_ReadChipTemperature_C(void);
uint16_t crc16_ccitt(const uint8_t *data, uint16_t len);
void BCM_SendFrame(uint8_t type, const uint8_t *payload, uint8_t len);
void BCM_ProcessFrame(uint8_t type, const uint8_t *payload, uint8_t len,
                      uint16_t recv_crc);
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

/**
 * @brief CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect). Computed
 *        identically on the Python side so a corrupted frame is dropped
 *        instead of silently mis-parsed.
 */
uint16_t crc16_ccitt(const uint8_t *data, uint16_t len) {
  uint16_t crc = 0xFFFF;
  for (uint16_t i = 0; i < len; i++) {
    crc ^= (uint16_t)((uint16_t)data[i] << 8);
    for (uint8_t b = 0; b < 8; b++) {
      if (crc & 0x8000) {
        crc = (uint16_t)((crc << 1) ^ 0x1021);
      } else {
        crc = (uint16_t)(crc << 1);
      }
    }
  }
  return crc;
}

/**
 * @brief Transmits one binary frame: START, TYPE, LEN, PAYLOAD, CRC16.
 */
void BCM_SendFrame(uint8_t type, const uint8_t *payload, uint8_t len) {
  uint8_t buf[2 + FRAME_MAX_PAYLOAD];
  buf[0] = type;
  buf[1] = len;
  if (len > 0) {
    memcpy(&buf[2], payload, len);
  }
  uint16_t crc = crc16_ccitt(buf, (uint16_t)(2 + len));

  uart_write(FRAME_START_BYTE);
  uart_write(type);
  uart_write(len);
  for (uint8_t i = 0; i < len; i++) {
    uart_write(payload[i]);
  }
  uart_write((uint8_t)(crc & 0xFF));
  uart_write((uint8_t)((crc >> 8) & 0xFF));
}

/**
 * @brief Validates a fully-received frame's CRC and dispatches it.
 */
void BCM_ProcessFrame(uint8_t type, const uint8_t *payload, uint8_t len,
                      uint16_t recv_crc) {
  uint8_t buf[2 + FRAME_MAX_PAYLOAD];
  buf[0] = type;
  buf[1] = len;
  if (len > 0) {
    memcpy(&buf[2], payload, len);
  }
  if (crc16_ccitt(buf, (uint16_t)(2 + len)) != recv_crc) {
    BCM_SendFrame(RESP_NACK, (void *)0, 0);
    return;
  }

  float val = 0.0f;
  if (len == sizeof(float)) {
    memcpy(&val, payload, sizeof(float));
  }

  switch (type) {
    case CMD_SET_PEDAL:
      if (val > 100.0f)
        val = 100.0f;
      if (val < 0.0f)
        val = 0.0f;
      bcm_in.pedal_force = val;
      BCM_SendFrame(RESP_ACK, (void *)0, 0);
      break;
    case CMD_SET_SPEED:
      bcm_in.vehicle_speed = val;
      BCM_SendFrame(RESP_ACK, (void *)0, 0);
      break;
    case CMD_SET_TEMP:
      bcm_in.brake_temp_celsius = val;
      BCM_SendFrame(RESP_ACK, (void *)0, 0);
      break;
    case CMD_SET_WEAR:
      bcm_in.brake_wear_pct = val;
      BCM_SendFrame(RESP_ACK, (void *)0, 0);
      break;
    case CMD_RESET:
      memset(&bcm_in, 0, sizeof(bcm_in));
      memset(&bcm_out, 0, sizeof(bcm_out));
      BCM_Init(&bcm_out);
      BCM_SendFrame(RESP_ACK, (void *)0, 0);
      break;
    default:
      BCM_SendFrame(RESP_NACK, (void *)0, 0);
      break;
  }
}

/**
 * @brief Reads the MCU's internal temperature sensor (ADC1 internal channel)
 *        and converts it to degrees Celsius using factory two-point
 *        calibration (TS_CAL1 @ 30C, TS_CAL2 @ 110C, per RM0368).
 * @retval Chip die temperature in degrees Celsius.
 */
int32_t BCM_ReadChipTemperature_C(void) {
  LL_ADC_REG_StartConversionSWStart(ADC1);
  while (!LL_ADC_IsActiveFlag_EOCS(ADC1)) {
  }
  uint16_t raw = LL_ADC_REG_ReadConversionData12(ADC1);
  LL_ADC_ClearFlag_EOCS(ADC1);

  int32_t ts_cal1 = (int32_t)(*TEMPSENSOR_CAL1_ADDR);
  int32_t ts_cal2 = (int32_t)(*TEMPSENSOR_CAL2_ADDR);

  int32_t temp_c = ((int32_t)raw - ts_cal1) *
                       (TEMPSENSOR_CAL2_TEMP - TEMPSENSOR_CAL1_TEMP) /
                       (ts_cal2 - ts_cal1) +
                   TEMPSENSOR_CAL1_TEMP;
  return temp_c;
}

void BCM_UART_RX_Callback(uint8_t rx_byte) {
  /* This is called by USART2_IRQHandler. Byte-level state machine for the
   * binary frame protocol: START, TYPE, LEN, PAYLOAD[LEN], CRC16 (lo, hi). */
  switch (s_frame_state) {
    case FRAME_WAIT_START:
      if (rx_byte == FRAME_START_BYTE) {
        s_frame_state = FRAME_WAIT_TYPE;
      }
      break;

    case FRAME_WAIT_TYPE:
      s_frame_type = rx_byte;
      s_frame_state = FRAME_WAIT_LEN;
      break;

    case FRAME_WAIT_LEN:
      s_frame_len = rx_byte;
      s_frame_payload_idx = 0;
      if (s_frame_len > sizeof(s_frame_payload)) {
        /* Malformed length: resync on the next start byte instead of
         * overrunning the payload buffer. */
        s_frame_state = FRAME_WAIT_START;
      } else {
        s_frame_state = (s_frame_len > 0) ? FRAME_WAIT_PAYLOAD : FRAME_WAIT_CRC1;
      }
      break;

    case FRAME_WAIT_PAYLOAD:
      s_frame_payload[s_frame_payload_idx++] = rx_byte;
      if (s_frame_payload_idx >= s_frame_len) {
        s_frame_state = FRAME_WAIT_CRC1;
      }
      break;

    case FRAME_WAIT_CRC1:
      s_frame_crc_recv = rx_byte;
      s_frame_state = FRAME_WAIT_CRC2;
      break;

    case FRAME_WAIT_CRC2:
      s_frame_crc_recv |= (uint16_t)((uint16_t)rx_byte << 8);
      BCM_ProcessFrame(s_frame_type, s_frame_payload, s_frame_len,
                       s_frame_crc_recv);
      s_frame_state = FRAME_WAIT_START;
      break;

    default:
      s_frame_state = FRAME_WAIT_START;
      break;
  }
}

void BCM_Periodic_Task(void) {
  /* This is called by SysTick_Handler every 1ms */
  s_tick_count++;

  /* Run BCM Logic Step @ 100Hz (every 10ms) */
  if (s_tick_count % 10 == 0) {
    BCM_Step(&bcm_in, &bcm_out);

    /* Trigger Telemetry Report @ 10Hz (every 100ms) */
    if (s_tick_count % 100 == 0) {
      g_telem_pending = 1;
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
  MX_ADC1_Init();
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
    if (g_telem_pending) {
      g_telem_pending = 0;
      TelemetryPayload_t telem;
      telem.tick = s_tick_count;
      telem.pedal = bcm_in.pedal_force;
      telem.speed = bcm_in.vehicle_speed;
      telem.wear = bcm_in.brake_wear_pct;
      telem.front = bcm_out.front_hydraulic_pressure;
      telem.rear = bcm_out.rear_hydraulic_pressure;
      telem.status_flag = bcm_out.status_flag;
      telem.chip_temp_c = BCM_ReadChipTemperature_C();
      BCM_SendFrame(RESP_TELEMETRY, (const uint8_t *)&telem,
                   (uint8_t)sizeof(telem));
    }
    
    __WFI(); /* Wait For Interrupt */
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
 * @brief ADC1 Initialization Function (internal chip temperature sensor)
 * @param None
 * @retval None
 */
static void MX_ADC1_Init(void) {
  /* Peripheral clock enable */
  LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_ADC1);

  /* ADC clock: PCLK2 (84MHz) / 4 = 21MHz, within the 36MHz ADC max */
  LL_ADC_SetCommonClock(__LL_ADC_COMMON_INSTANCE(ADC1),
                        LL_ADC_CLOCK_SYNC_PCLK_DIV4);
  LL_ADC_SetCommonPathInternalCh(__LL_ADC_COMMON_INSTANCE(ADC1),
                                 LL_ADC_PATH_INTERNAL_TEMPSENSOR);

  LL_ADC_SetResolution(ADC1, LL_ADC_RESOLUTION_12B);
  LL_ADC_SetDataAlignment(ADC1, LL_ADC_DATA_ALIGN_RIGHT);
  LL_ADC_REG_SetTriggerSource(ADC1, LL_ADC_REG_TRIG_SOFTWARE);
  LL_ADC_REG_SetContinuousMode(ADC1, LL_ADC_REG_CONV_SINGLE);
  LL_ADC_REG_SetSequencerLength(ADC1, LL_ADC_REG_SEQ_SCAN_DISABLE);
  LL_ADC_REG_SetSequencerRanks(ADC1, LL_ADC_REG_RANK_1,
                               LL_ADC_CHANNEL_TEMPSENSOR);
  /* Temp sensor requires a long sampling time (>= 10us min) */
  LL_ADC_SetChannelSamplingTime(ADC1, LL_ADC_CHANNEL_TEMPSENSOR,
                                LL_ADC_SAMPLINGTIME_480CYCLES);

  LL_ADC_Enable(ADC1);
  /* Let the ADC and temp sensor internal paths stabilize before first read */
  LL_mDelay(1);
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
