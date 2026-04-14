# 🏎️ Brake ECU - Comprehensive Software Requirements

This document is designed to guide a developer from basic logic implementation to safety-critical automotive software patterns.

## Phase 1: Core Fundamentals (The Basics)
| ID | Title | Description | C Skills Used |
|---|---|---|---|
| **SWE_REQ_001** | **Initialization** | On power-on, reset all output signals (pressure = 0.0, flags = 0x00). | Pointers, Struct Reset |
| **SWE_REQ_003** | **Input Clamping** | `pedal_force` must be clamped to [0.0, 100.0%]. | Floating point comparison |
| **SWE_REQ_004** | **1:1 Mapping** | `hydraulic_pressure` = `pedal_force` in normal conditions. | Basic Assignment |

## Phase 2: Signal Quality & Diagnostics (The "Real World")
| ID | Title | Description | C Skills Used |
|---|---|---|---|
| **SWE_REQ_006** | **Wear Detection** | If `sensor_volt` > 4.5V, bit 3 of `status_flag` shall be set to indicate a wear warning. | Bitwise Operations (`|=`) |
| **SWE_REQ_007** | **Thermal Latching** | If Temp > 200°C, set bit 1. Only clear after **3 consecutive cycles** of temperature ≤ 200°C. | Static variables (Counters) |
| **SWE_REQ_011** | **Plausibility Check** | If Pedal > 50% but Speed doesn't drop for 5 frames, set "Stuck Pedal" bit 4. Clear after 3 frames of decrease. | State persistence |
| **SWE_REQ_016** | **Signal Range Check**| If `pedal_force` is exactly 0.0V or 5.0V (Electrical fault), set "Sensor Invalid" bit 6 and force safe pressure. | Error Handling |

## Phase 3: Control Algorithms (Energy & Safety)
| ID | Title | Description | C Skills Used |
|---|---|---|---|
| **SWE_REQ_002** | **ABS Reduction** | If Speed > 100 km/h AND Pedal > 80%, multiply pressure by **0.62**. | Constants (`#define`) |
| **SWE_REQ_014** | **Regen Blending** | If `motor_torque` > 0, subtract (Torque / 10) from Hydraulic Pressure. Clamp to 0. | Unit Conversion / Saturation |
| **SWE_REQ_010** | **Emergency Assist**| If Pedal slam (>90%) and Speed > 60, boost pressure to 100.0 Bar. | Threshold Logic |
| **SWE_REQ_013** | **Electronic Brake Dist.** | Rear pressure (new output) = Front pressure * 0.7 if Deceleration > 5 m/s². | Derivatives / Dynamics |

## Phase 4: Time-Based Features (Advanced)
| ID | Title | Description | C Skills Used |
|---|---|---|---|
| **SWE_REQ_009** | **Hill Start Assist** | If speed=0 and pedal released from >80%, hold 30 Bar for **2.0 seconds** or until speed > 5 km/h. | Timers (10ms ticks) |
| **SWE_REQ_012** | **Disc Wiping** | If `rain_detected` AND speed > 50, apply 2 Bar for **1 sec** every **60 sec**. | Nested Counters |
| **SWE_REQ_015** | **Heartbeat** | Status bits 5-7 shall be a 3-bit rolling counter (0-7) incrementing every call. | Bit Shifting / Wrapping |

## Phase 5: The "Boss Level" (Complex Systems)
| ID | Title | Description | C Skills Used |
|---|---|---|---|
| **SWE_REQ_017** | **Parameter Tuning** | All thresholds (200°C, 30 Bar, etc.) stored in a "Calibration" struct. | Config Structs / Const pointers |
| **SWE_REQ_018** | **Event Logger** | Maintain a 5-item circular buffer of the last "Status Flag" changes. | Circular Buffers / Arrays |
