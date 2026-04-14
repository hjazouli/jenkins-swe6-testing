# Software Requirements Specification (SRS) - Brake ECU
**Project:** SWE6-Safety-Brake  
**Owner:** Antigravity AI / [User Name]  
**Version:** 2.1.0  
**Compliance:** ASPICE SWE.1 / ISO 26262  

---

## 1. System Task Execution
| ID | Requirement Description | ASIL | Verification |
|---|---|---|---|
| **SSR_SYS_001** | The software shall execute the `Brake_Control_Step` task periodically every **10ms ± 0.5ms**. | D | HiL |
| **SSR_SYS_002** | The system shall implement a 3-bit rolling heartbeat (0-7) in `status_flag` [bits 5:7] to detect task freezes. | B | UT |

## 2. Functional Control Logic
| ID | Title | Requirement Description | ASIL | Rationale |
|---|---|---|---|---|
| **SSR_FCN_001** | **ABS reduction** | If `vehicle_speed` > 100.0 km/h AND `pedal_force` > 80.0%, the hydraulic pressure shall be reduced by a factor of 0.62. | D | Prevent wheel lockup and maintain steerability at high speed. |
| **SSR_FCN_002** | **Regen Blending** | If `motor_regen_torque` is available, the hydraulic request shall be reduced by `(torque / 10)`. The final pressure shall not be < 0.0 Bar. | QM | Energy efficiency / Reduced wear. |
| **SSR_FCN_003** | **EBD Control** | If longitudinal deceleration > 5.0 m/s², the `rear_pressure` shall be limited to 70% of `front_pressure`. | D | Prevent oversteering during high deceleration. |

## 3. Safety & Diagnostic Requirements
| ID | Title | Requirement Description | ASIL | Rationale |
|---|---|---|---|---|
| **SSR_SAF_001** | **Signals Clamping**| The input `pedal_force` shall be clamped to the range [0.0, 100.0] before any arithmetic operations. | B | Defensive programming to prevent overflow/unexpected logic. |
| **SSR_SAF_002** | **Signal Quality** | If `pedal_force_volt` sensor returns < 0.5V or > 4.5V (Electrical fault), the system shall set **Bit 4** (Fail-Safe) and force pressure to 0 Bar. | D | Prevent unintended braking due to electrical harness faults. |
| **SSR_SAF_003** | **Thermal Latching**| If `brake_temp` > 200°C, Bit 1 (Overheat) shall be latched. Latch clear requires 3 consecutive cycles below threshold. | B | Protect hydraulic fluid from boiling / Fire prevention. |
| **SSR_SAF_004** | **Thermal Clamp** | If Bit 1 (Overheat) is set, output pressure shall be strictly saturated at **50.0 Bar**. | D | Safety fallback when component integrity is compromised. |

## 4. Advanced Driver Assistance (ADAS)
| ID | Title | Requirement Description | ASIL | Timing |
|---|---|---|---|---|
| **SSR_ADA_001** | **Hill Start Assist**| Maintain 30 Bar for **2.0s** after pedal release if `speed == 0` and previous pedal was > 80%. | A | Comfort feature / Roll-back prevention. |
| **SSR_ADA_002** | **Disc Wiping** | If `rain_detected` == TRUE AND `speed` > 50 km/h, apply 2.0 Bar for 1.0s every 60s. | QM | Performance maintenance in wet conditions. |

---
---
## 5. Communication Interface (CAN Matrix)
| ID | Message Name | Byte Offset | Signal Name | Data Type | Notes |
|---|---|---|---|---|---|
| **0x200** | BRAKE_CMD | 3 | Pedal Force | uint8 | 0-100% |
| | | 1-2 | Pedal Voltage | uint16 | mV (Big Endian) |
| **0x210** | VEH_SPEED | 2 | Speed | uint8 | km/h |
| | | 3 | Rain Sensor | uint8 | [0: Dry, 1: Rain] |
| **0x300** | PRESSURE_FB | 3 | Output Pressure | uint8 | Bar |
| **0x400** | STATUS_FB | 0 | Status Flags | uint8 | [Bit 4: Fail-Safe, Bit 1: Overheat] |
| | | | Heartbeat | | [Bits 5:7: 0-7 Counter] |

**Verification Legend:**
- **UT:** Unit Test (Unity/GCov)
- **HiL:** Hardware-in-the-Loop Simulation
- **SiL:** Software-in-the-Loop (Virtual ECU)
