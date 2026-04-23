/**
  ******************************************************************************
  * @file    stm32f4xx_ll_gpio.h
  * @author  MCD Application Team
  * @brief   Header file of GPIO LL module.
  ******************************************************************************
  */

#ifndef __STM32F4xx_LL_GPIO_H
#define __STM32F4xx_LL_GPIO_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx.h"

/** @defgroup GPIO_LL_EC_PIN PIN
  * @{
  */
#define LL_GPIO_PIN_0                      GPIO_BSRR_BS_0
#define LL_GPIO_PIN_1                      GPIO_BSRR_BS_1
#define LL_GPIO_PIN_2                      GPIO_BSRR_BS_2
#define LL_GPIO_PIN_3                      GPIO_BSRR_BS_3
#define LL_GPIO_PIN_4                      GPIO_BSRR_BS_4
#define LL_GPIO_PIN_5                      GPIO_BSRR_BS_5
#define LL_GPIO_PIN_6                      GPIO_BSRR_BS_6
#define LL_GPIO_PIN_7                      GPIO_BSRR_BS_7
#define LL_GPIO_PIN_8                      GPIO_BSRR_BS_8
#define LL_GPIO_PIN_9                      GPIO_BSRR_BS_9
#define LL_GPIO_PIN_10                     GPIO_BSRR_BS_10
#define LL_GPIO_PIN_11                     GPIO_BSRR_BS_11
#define LL_GPIO_PIN_12                     GPIO_BSRR_BS_12
#define LL_GPIO_PIN_13                     GPIO_BSRR_BS_13
#define LL_GPIO_PIN_14                     GPIO_BSRR_BS_14
#define LL_GPIO_PIN_15                     GPIO_BSRR_BS_15
/**
  * @}
  */

/** @defgroup GPIO_LL_EC_MODE Mode
  * @{
  */
#define LL_GPIO_MODE_INPUT                 (0x00000000U) /*!< Select input mode */
#define LL_GPIO_MODE_OUTPUT                GPIO_MODER_MODER0_0  /*!< Select output mode */
#define LL_GPIO_MODE_ALTERNATE             GPIO_MODER_MODER0_1  /*!< Select alternate function mode */
#define LL_GPIO_MODE_ANALOG                GPIO_MODER_MODER0    /*!< Select analog mode */
/**
  * @}
  */

/** @defgroup GPIO_LL_EC_SPEED Output Speed
  * @{
  */
#define LL_GPIO_SPEED_FREQ_LOW             (0x00000000U) /*!< Select I/O low output speed    */
#define LL_GPIO_SPEED_FREQ_MEDIUM          GPIO_OSPEEDR_OSPEED0_0 /*!< Select I/O medium output speed */
#define LL_GPIO_SPEED_FREQ_HIGH            GPIO_OSPEEDR_OSPEED0_1 /*!< Select I/O high output speed   */
#define LL_GPIO_SPEED_FREQ_VERY_HIGH       GPIO_OSPEEDR_OSPEED0   /*!< Select I/O very high output speed */
/**
  * @}
  */

/** @defgroup GPIO_LL_EC_AF Alternate Function
  * @{
  */
#define LL_GPIO_AF_0                       (0x00000000U) /*!< Select alternate function 0 */
#define LL_GPIO_AF_1                       (0x00000001U) /*!< Select alternate function 1 */
#define LL_GPIO_AF_2                       (0x00000002U) /*!< Select alternate function 2 */
#define LL_GPIO_AF_3                       (0x00000003U) /*!< Select alternate function 3 */
#define LL_GPIO_AF_4                       (0x00000004U) /*!< Select alternate function 4 */
#define LL_GPIO_AF_5                       (0x00000005U) /*!< Select alternate function 5 */
#define LL_GPIO_AF_6                       (0x00000006U) /*!< Select alternate function 6 */
#define LL_GPIO_AF_7                       (0x00000007U) /*!< Select alternate function 7 */
/**
  * @}
  */

/* Helper macro for pin indexing */
#define GPIO_GET_INDEX(__PIN__) ( \
    ((__PIN__) == LL_GPIO_PIN_0)  ? 0U  : \
    ((__PIN__) == LL_GPIO_PIN_1)  ? 1U  : \
    ((__PIN__) == LL_GPIO_PIN_2)  ? 2U  : \
    ((__PIN__) == LL_GPIO_PIN_3)  ? 3U  : \
    ((__PIN__) == LL_GPIO_PIN_4)  ? 4U  : \
    ((__PIN__) == LL_GPIO_PIN_5)  ? 5U  : \
    ((__PIN__) == LL_GPIO_PIN_6)  ? 6U  : \
    ((__PIN__) == LL_GPIO_PIN_7)  ? 7U  : \
    ((__PIN__) == LL_GPIO_PIN_8)  ? 8U  : \
    ((__PIN__) == LL_GPIO_PIN_9)  ? 9U  : \
    ((__PIN__) == LL_GPIO_PIN_10) ? 10U : \
    ((__PIN__) == LL_GPIO_PIN_11) ? 11U : \
    ((__PIN__) == LL_GPIO_PIN_12) ? 12U : \
    ((__PIN__) == LL_GPIO_PIN_13) ? 13U : \
    ((__PIN__) == LL_GPIO_PIN_14) ? 14U : \
    ((__PIN__) == LL_GPIO_PIN_15) ? 15U : 0U)

/**
  * @brief  Configure gpio mode for a dedicated pin on a specific GPIO port.
  * @param  GPIOx GPIO Port
  * @param  Pin This parameter can be one of the following values: LL_GPIO_PIN_0..15
  * @param  Mode This parameter can be one of the following values: LL_GPIO_MODE_INPUT..ANALOG
  * @retval None
  */
static inline void LL_GPIO_SetPinMode(GPIO_TypeDef *GPIOx, uint32_t Pin, uint32_t Mode)
{
  MODIFY_REG(GPIOx->MODER, (GPIO_MODER_MODER0 << (GPIO_GET_INDEX(Pin) * 2U)), (Mode << (GPIO_GET_INDEX(Pin) * 2U)));
}

/**
  * @brief  Configure gpio speed for a dedicated pin on a specific GPIO port.
  * @param  GPIOx GPIO Port
  * @param  Pin This parameter can be one of the following values: LL_GPIO_PIN_0..15
  * @param  Speed This parameter can be one of the following values: LL_GPIO_SPEED_FREQ_LOW..VERY_HIGH
  * @retval None
  */
static inline void LL_GPIO_SetPinSpeed(GPIO_TypeDef *GPIOx, uint32_t Pin, uint32_t Speed)
{
  MODIFY_REG(GPIOx->OSPEEDR, (GPIO_OSPEEDR_OSPEED0 << (GPIO_GET_INDEX(Pin) * 2U)), (Speed << (GPIO_GET_INDEX(Pin) * 2U)));
}

/**
  * @brief  Configure gpio alternate function for a dedicated pin on a specific GPIO port.
  * @param  GPIOx GPIO Port
  * @param  Pin This parameter can be one of the following values: LL_GPIO_PIN_0..15
  * @param  Alternate This parameter can be one of the following values: LL_GPIO_AF_0..15
  * @retval None
  */
static inline void LL_GPIO_SetAFPin_0_7(GPIO_TypeDef *GPIOx, uint32_t Pin, uint32_t Alternate)
{
  MODIFY_REG(GPIOx->AFR[0], (0xFU << (GPIO_GET_INDEX(Pin) * 4U)), (Alternate << (GPIO_GET_INDEX(Pin) * 4U)));
}

static inline void LL_GPIO_SetAFPin_8_15(GPIO_TypeDef *GPIOx, uint32_t Pin, uint32_t Alternate)
{
  MODIFY_REG(GPIOx->AFR[1], (0xFU << ((GPIO_GET_INDEX(Pin) - 8U) * 4U)), (Alternate << ((GPIO_GET_INDEX(Pin) - 8U) * 4U)));
}

/**
  * @brief  Toggle data value of a specific pin of a specific GPIO port.
  */
static inline void LL_GPIO_TogglePin(GPIO_TypeDef *GPIOx, uint32_t Pin)
{
  WRITE_REG(GPIOx->ODR, READ_REG(GPIOx->ODR) ^ Pin);
}

#ifdef __cplusplus
}
#endif

#endif /* __STM32F4xx_LL_GPIO_H */
