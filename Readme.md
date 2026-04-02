# Project Analysis: SWE6-Test

## 🚗 Overview

The **SWE6-Test** project is a simulation of an automotive CI/CD pipeline designed for Software Engineering (SWE.6) unit and integration testing. It models the workflow of building, flashing, and testing firmware for an Electronic Control Unit (ECU), specifically a **Brake Controller**.

## 📂 Project Structure

```text
SWE6-Test/
├── Jenkinsfile              # CI/CD pipeline definition
├── Makefile                 # Build instructions for C firmware
├── requirements.txt         # Python dependencies (pytest, python-can, etc.)
├── src/
│   └── main.c                # Mock ECU firmware source
├── tests/
│   ├── conftest.py          # Pytest fixtures and CAN setup
│   └── test_brake_controller.py # Automotive logic test cases
├── scripts/
│   ├── mock_lauterbach.py   # Simulates ECU flashing
│   ├── mock_polarion_server.py # Simulates ALM server
│   └── polarion_upload.py   # Test results uploader
└── build/                   # Compiled artifacts (firmware.elf)
```

## 🛠️ Key Components

### 1. Mock ECU Firmware (`src/main.c`)

A minimal C application that simulates the base software for a **TC397 (Infineon TriCore)** ECU. It provides basic initialization logging.

### 2. CI/CD Pipeline (`Jenkinsfile`)

The pipeline automates the entire lifecycle:

1.  **Checkout**: Retrieves source code.
2.  **Build**: Compiles `main.c` into `firmware.elf` using `gcc`.
3.  **Flash**: Executes `mock_lauterbach.py` to simulate the deployment of firmware to hardware.
4.  **Pytest**: Runs automated functional tests against the virtual ECU using `python-can`.
5.  **Report & Upload**: Generates HTML/JUnit reports and pushes them to a mock Polarion server.

### 3. Automated Testing (`tests/`)

Tests are written in Python using `pytest` and `python-can`:

- **Brake Pressure Response**: Verifies the ECU responds correctly to brake pedal signals (CAN ID `0x200` & `0x300`).
- **ABS Logic**: Validates Anti-lock Braking System (ABS) activation parameters (CAN ID `0x210` & `0x400`) based on vehicle speed and pedal force.

### 4. Integration Tooling (`scripts/`)

- **Flashing Simulation**: `mock_lauterbach.py` imitates the behavior of industry-standard debuggers.
- **ALM Integration**: `polarion_upload.py` demonstrates how test results are integrated back into ALM (Application Lifecycle Management) tools for traceability.

## 📈 Summary of Technologies

- **Languages**: C, Python
- **Build System**: Make/GCC
- **CI/CD**: Jenkins
- **Testing**: Pytest, python-can
- **Reporting**: JUnit, HTML (pytest-html)
- **Target**: Infineon TriCore TC397 (Mocked)
Auto-triggered by Git Hook
