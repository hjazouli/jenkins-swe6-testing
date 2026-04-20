#include "brake_logic.h"

/* ========================================================================= */
/*                          INTERNAL PERSISTENT STATE                         */
/* ========================================================================= */
static uint8_t fault_latch = 0x00;
static uint8_t recovery_counter = 0;

/* Plausibility & EBD states */
static float plaus_last_speed = 0.0f;
static float ebd_last_speed = 0.0f;
static uint8_t plaus_counter = 0;
static uint8_t plaus_latch = 0x00;
static uint8_t plaus_recovery_counter = 0;
static uint8_t heartbeat_cnt = 0;

/* ========================================================================= */
/*                          STATIC FUNCTION PROTOTYPES                        */
/* ========================================================================= */
static void Hydraulic_Mapping_ABS_Inactive(float validated_pedal,
                                           BrakeOutput_t* output);
static void Fault_Latching_Overheat(const BrakeInput_t* input,
                                    BrakeOutput_t* output);
static void Thermal_Safety_Clamp(const BrakeInput_t* input,
                                 BrakeOutput_t* output);
static void Emergency_Stop_Assistance(const BrakeInput_t* input,
                                      BrakeOutput_t* output);
static void Rolling_Plausibility_Check(const BrakeInput_t* input,
                                       BrakeOutput_t* output);
static void Apply_Regen_Blending(const BrakeInput_t* input,
                                 BrakeOutput_t* output);
static void Hill_Start_Assist(const BrakeInput_t* input, BrakeOutput_t* output);
static void Split_Brake_Pressure(const BrakeInput_t* input,
                                 BrakeOutput_t* output);
/* ========================================================================= */
/*                          PUBLIC INTERFACE FUNCTIONS                        */
/* ========================================================================= */

/**
 * @brief Initialize the Brake Control internal state.
 * @requirement SWE_REQ_001
 */
void Brake_Control_Init(BrakeOutput_t* output) {
  if (output == (void*)0) return;

  output->hydraulic_pressure = 0.0f;
  output->abs_active = 0;
  output->status_flag = 0x00;

  /* Reset internal latches */
  fault_latch = 0x00;
  recovery_counter = 0;

  /* Reset plausibility & EBD history */
  plaus_last_speed = 0.0f;
  ebd_last_speed = 0.0f;
  plaus_counter = 0;
  plaus_latch = 0x00;
  plaus_recovery_counter = 0;

  /* SWE_REQ_015: Reset heartbeat */
  heartbeat_cnt = 0;

  output->front_hydraulic_pressure = 0.0f;
  output->rear_hydraulic_pressure = 0.0f;
}

/* ========================================================================= */
/* @brief Main Periodic Task (ASW Logic Step). Called every 10ms.         */
/* @requirement SWE_REQ_002, SWE_REQ_003, SWE_REQ_006, SWE_REQ_007,
 * SWE_REQ_008,*/
/* @requirement SWE_REQ_010, SWE_REQ_011                                    */
/* ========================================================================= */
void Brake_Control_Step(const BrakeInput_t* input, BrakeOutput_t* output) {
  if ((input == (void*)0) || (output == (void*)0)) return;

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
  Apply_Regen_Blending(input, output);
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

  /* SWE_REQ_009: Hill Start Assist */
  Hill_Start_Assist(input, output);

  /* SWE_REQ_015: Shift 3-bit counter to bits 5-7 and OR into status */
  output->status_flag |= (uint8_t)(heartbeat_cnt << 5);

  /* Increment for next frame (3-bit wrap-around 0-7) */
  heartbeat_cnt = (uint8_t)((heartbeat_cnt + 1) & 0x07);

  Split_Brake_Pressure(input, output);
}

/* ========================================================================= */
/*                          INTERNAL HELPER FUNCTIONS                         */
/* ========================================================================= */

/* ========================================================================= */
/* @brief Handles 1:1 pressure mapping for non-ABS scenarios.                */
/* @requirement SWE_REQ_004                                                  */
/* ========================================================================= */
static void Hydraulic_Mapping_ABS_Inactive(float validated_pedal,
                                           BrakeOutput_t* output) {
  if (output->abs_active == 0) {
    output->hydraulic_pressure = validated_pedal;
  }
}

/* ========================================================================= */
/* @brief Implements the 3-frame fault latching logic for thermal safety.    */
/* @requirement SWE_REQ_007                                                  */
/* ========================================================================= */
static void Fault_Latching_Overheat(const BrakeInput_t* input,
                                    BrakeOutput_t* output) {
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

/* ========================================================================= */
/* @brief Handes brake protection when they are hot (Safety Clamp).          */
/* @requirement SWE_REQ_008                                                  */
/* ========================================================================= */
static void Thermal_Safety_Clamp(const BrakeInput_t* input,
                                 BrakeOutput_t* output) {
  if ((output->status_flag & 0x02) && (output->hydraulic_pressure > 50.0f)) {
    output->hydraulic_pressure = 50.0f;
  }
}

/* ========================================================================= */
/* @brief Handles emergency stop assistance when the driver slams the brakes. */
/* @requirement SWE_REQ_010                                                  */
/* ========================================================================= */
static void Emergency_Stop_Assistance(const BrakeInput_t* input,
                                      BrakeOutput_t* output) {
  if (input->pedal_force > 90.0f && input->vehicle_speed > 60.0f) {
    output->hydraulic_pressure = 100.0f;
  }
}

/* ========================================================================= */
/* @brief Detect if the pedal sensor is stuck or giving "impossible" data.   */
/* @requirement SWE_REQ_011                                                  */
/* ========================================================================= */
static void Rolling_Plausibility_Check(const BrakeInput_t* input,
                                       BrakeOutput_t* output) {
  /* Condition: Pedal is pressed hard but speed is NOT decreasing (>=) */

  if ((input->vehicle_speed >= plaus_last_speed) &&
      (input->pedal_force > 50.0f)) {
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
  plaus_last_speed = input->vehicle_speed;

  /* Apply latched fault to status */
  output->status_flag |= plaus_latch;
}

/* ========================================================================= */
/* @brief Applies regen blending to the hydraulic pressure.                   */
/* @requirement SWE_REQ_014                                                  */
/* ========================================================================= */
static void Apply_Regen_Blending(const BrakeInput_t* input,
                                 BrakeOutput_t* output) {
  if (input->motor_torque > 0) {
    float equivalent_regen_pressure = input->motor_torque / TORQUE_TO_BAR_RATIO;
    float diff = output->hydraulic_pressure - equivalent_regen_pressure;
    if (diff > 0) {
      output->hydraulic_pressure = diff;
    } else {
      output->hydraulic_pressure = 0.0f;
    }
  }
}

/* ========================================================================= */
/* @brief Handles Hill Start Assist - Maintains pressure when releasing
 * brakes.*/
/* @requirement SWE_REQ_009                                                  */
/* ========================================================================= */

static void Hill_Start_Assist(const BrakeInput_t* input,
                              BrakeOutput_t* output) {
  static uint16_t hsa_timer = 0;

  /* 1. Arming condition: Car stopped and brakes applied hard */
  if (input->vehicle_speed == 0.0f && input->pedal_force > 80.0f) {
    hsa_timer = HSA_HOLD_DURATION_CYCLES;
  }

  /* 2. Holding logic: Only if armed and driver releases the pedal */
  if (hsa_timer > 0) {
    if (input->pedal_force < 5.0f) {
      /* Maintenance mode: Overwrite the hydraulic pressure */
      output->hydraulic_pressure = HSA_HOLD_PRESSURE;
      hsa_timer--;
    }

    /* 3. Abort/Release: If car moves faster than threshold or time expires */
    if (input->vehicle_speed > HSA_RELEASE_SPEED_THRESHOLD) {
      hsa_timer = 0;
    }
  }
}

/* ========================================================================= */
/* @brief Splits the hydraulic pressure between front and rear brakes.       */
/* @requirement SWE_REQ_013                                                  */
/* ========================================================================= */
static void Split_Brake_Pressure(const BrakeInput_t* input,
                                 BrakeOutput_t* output) {
  float deceleration = ((ebd_last_speed - input->vehicle_speed) / 0.01f) / 3.6f;

  if (deceleration > 5.0f) {
    output->front_hydraulic_pressure = output->hydraulic_pressure;
    output->rear_hydraulic_pressure = output->front_hydraulic_pressure * 0.7f;
  } else {
    output->rear_hydraulic_pressure = output->hydraulic_pressure;
    output->front_hydraulic_pressure = output->hydraulic_pressure;
  }
  ebd_last_speed = input->vehicle_speed; /* first vehicle vehicle speed */
}
