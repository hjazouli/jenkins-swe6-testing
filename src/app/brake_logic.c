#include "brake_logic.h"

/* ========================================================================= */
/*                          INTERNAL PERSISTENT STATE                         */
/* ========================================================================= */
static uint8_t fault_latch = 0x00;
static uint8_t recovery_counter = 0;

/* Plausibility states */
static float last_vehicle_speed = 0.0f;
static uint8_t plaus_counter = 0;
static uint8_t plaus_latch = 0x00;
static uint8_t plaus_recovery_counter = 0;

/* ========================================================================= */
/*                          STATIC FUNCTION PROTOTYPES                        */
/* ========================================================================= */
static void Hydraulic_Mapping_ABS_Inactive(float validated_pedal,
                                           BrakeOutput_t *output);
static void Fault_Latching_Overheat(const BrakeInput_t *input,
                                    BrakeOutput_t *output);
static void Thermal_Safety_Clamp(const BrakeInput_t *input,
                                 BrakeOutput_t *output);
static void Emergency_Stop_Assistance(const BrakeInput_t *input,
                                      BrakeOutput_t *output);
static void Rolling_Plausibility_Check(const BrakeInput_t *input,
                                       BrakeOutput_t *output);

/* ========================================================================= */
/*                          PUBLIC INTERFACE FUNCTIONS                        */
/* ========================================================================= */

/**
 * @brief Initialize the Brake Control internal state.
 * @requirement SWE_REQ_001
 */
void Brake_Control_Init(BrakeOutput_t *output) {
  if (output == (void *)0) return;

  output->hydraulic_pressure = 0.0f;
  output->abs_active = 0;
  output->status_flag = 0x00;

  /* Reset internal latches */
  fault_latch = 0x00;
  recovery_counter = 0;
  
  /* Reset plausibility */
  last_vehicle_speed = 0.0f;
  plaus_counter = 0;
  plaus_latch = 0x00;
  plaus_recovery_counter = 0;
}

/**
 * @brief Main Periodic Task (ASW Logic Step). Called every 10ms.
 * @requirement SWE_REQ_002, SWE_REQ_003, SWE_REQ_006, SWE_REQ_007, SWE_REQ_008,
 * SWE_REQ_010, SWE_REQ_011
 */
void Brake_Control_Step(const BrakeInput_t *input, BrakeOutput_t *output) {
  if ((input == (void *)0) || (output == (void *)0)) return;

  /* -----------------------------------------------------------------------
   * 1. INPUT VALIDATION & CLAMPING (SWE_REQ_003)
   * ----------------------------------------------------------------------- */
  float validated_pedal = input->pedal_force;
  if (validated_pedal > 100.0f) {
    validated_pedal = 100.0f;
  } else if (validated_pedal < 0.0f) {
    validated_pedal = 0.0f;
  }

  /* -----------------------------------------------------------------------
   * 2. ABS & HYDRAULIC CONTROL (SWE_REQ_002, SWE_REQ_004)
   * ----------------------------------------------------------------------- */
  if (input->vehicle_speed > 100.0f && validated_pedal > 80.0f) {
    output->hydraulic_pressure =
        validated_pedal * ABS_PRESSURE_REDUCTION_FACTOR;
    output->abs_active = 1;
  } else {
    output->abs_active = 0;
    Hydraulic_Mapping_ABS_Inactive(validated_pedal, output);
  }

  /* -----------------------------------------------------------------------
   * 3. DIAGNOSTICS & STATUS MONITORING (SWE_REQ_006, SWE_REQ_007, SWE_REQ_011)
   * ----------------------------------------------------------------------- */
  output->status_flag = 0x00;

  if (output->abs_active) {
    output->status_flag |= 0x01;
  }

  if (input->sensor_wear_volt > BRAKE_WEAR_VOLTAGE_THRESHOLD) {
    output->status_flag |= 0x08;
  }

  Fault_Latching_Overheat(input, output);
  Rolling_Plausibility_Check(input, output);

  /* -----------------------------------------------------------------------
   * 4. SAFETY REACTIONS & ASSISTANCE (SWE_REQ_008, SWE_REQ_010)
   * ----------------------------------------------------------------------- */
  Emergency_Stop_Assistance(input, output);
  Thermal_Safety_Clamp(input, output);
}

/* ========================================================================= */
/*                          INTERNAL HELPER FUNCTIONS                         */
/* ========================================================================= */

/**
 * @brief Handles 1:1 pressure mapping for non-ABS scenarios.
 * @requirement SWE_REQ_004
 */
static void Hydraulic_Mapping_ABS_Inactive(float validated_pedal,
                                           BrakeOutput_t *output) {
  if (output->abs_active == 0) {
    output->hydraulic_pressure = validated_pedal;
  }
}

/**
 * @brief Implements the 3-frame fault latching logic for thermal safety.
 * @requirement SWE_REQ_007
 */
static void Fault_Latching_Overheat(const BrakeInput_t *input,
                                    BrakeOutput_t *output) {
  if (input->brake_temp_celsius > BRAKE_OVERHEAT_THRESHOLD_C) {
    fault_latch |= 0x02;
    recovery_counter = 0;
  } else {
    if (fault_latch & 0x02) {
      recovery_counter++;
      if (recovery_counter >= 3) {
        fault_latch &= ~0x02;
        recovery_counter = 0;
      }
    }
  }
  output->status_flag |= fault_latch;
}

/**
 * @brief Handes brake protection when they are hot (Safety Clamp).
 * @requirement SWE_REQ_008
 */
static void Thermal_Safety_Clamp(const BrakeInput_t *input,
                                 BrakeOutput_t *output) {
  if ((output->status_flag & 0x02) && (output->hydraulic_pressure > 50.0f)) {
    output->hydraulic_pressure = 50.0f;
  }
}

/**
 * @brief Handles emergency stop assistance when the driver slams the brakes.
 * @requirement SWE_REQ_010
 */
static void Emergency_Stop_Assistance(const BrakeInput_t *input, BrakeOutput_t *output) 
{
  if (input->pedal_force > 90.0f && input->vehicle_speed > 60.0f) 
  {
    output->hydraulic_pressure = 100.0f;
  }
}

/**
 * @brief Detect if the pedal sensor is stuck or giving "impossible" data.
 * @requirement SWE_REQ_011
 */
static void Rolling_Plausibility_Check(const BrakeInput_t *input,BrakeOutput_t *output) 
{
  /* Condition: Pedal is pressed hard but speed is NOT decreasing (>=) */

  if ((input->vehicle_speed >= last_vehicle_speed) && (input->pedal_force > 50.0f)) 
  {
    plaus_counter++;
    if (plaus_counter >= 5) {
      plaus_latch = 0x10;
      plaus_recovery_counter = 0;
    }
  } 
  
  else {
    plaus_counter = 0;
    /* Recovery logic: Must see decreasing speed for 3 frames to clear */
    if (plaus_latch & 0x10) {
       plaus_recovery_counter++;
       if (plaus_recovery_counter >= 3) {
           plaus_latch = 0x00;
           plaus_recovery_counter = 0;
       }
    }
  }

  /* Update for next cycle comparison */
  last_vehicle_speed = input->vehicle_speed;
  
  /* Apply latched fault to status */
  output->status_flag |= plaus_latch;
}
