# BCM HiL Project Architecture

This diagram illustrates the unified Hardware-in-the-Loop (HiL) and Software-in-the-Loop (SiL) framework developed for the STM32 Brake Control Module.

![HiL Architecture Diagram](../../docs/hardware/architecture_hil.png)

### Key Components:
- **Unified Target Fixture**: Abstracted Pytest layer that switches between hardware and simulation.
- **Greedy Listener**: Non-blocking UART parser on the STM32 that ensures zero-loss command reception.
- **Bi-Directional Interface**: Stimulus (Requests) sent over USB-CDC and Response (Telemetry) captured via UART.
