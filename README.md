# SWE6-Test: ECU Firmware CI/CD & Verification Framework

## 📌 Mission Overview

The **SWE6-Test** repository is a high-fidelity simulation of an automotive software development environment. It demonstrates how to achieve **ASPICE SWE.6 (Software Unit Test)** and **SWE.5 (Software Integration Test)** compliance using a modern CI/CD stack.

This project simulates the development of a **Brake Control ECU** (Infineon TC397 target), moving from raw C source code to a fully verified, coverage-tracked, and automated pipeline.

---

## 🏗️ System Architecture

### 1. Firmware Layers (C Source)

The firmware is structured using a simplified **AUTOSAR-like** layered architecture:

- **ASW (Application Software Layer)**:
  - `src/app/brake_logic.c`: Contains the core safety logic, including hydraulic pressure calculations, ABS (Anti-lock Braking System) algorithms, and thermal/wear monitoring.
- **BSW (Base Software Layer)**:
  - `src/bsw/schm.c`: A static scheduler implementing a 10ms task cycle for real-time responsiveness.
  - `src/bsw/can_stack.c`: Simulates the communication stack. It includes a **Mock CAN Buffer** to allow unit testing of BSW without actual hardware or transceiver drivers.

### 2. Verification Layers (The "Boring" Details)

#### **Layer A: Unit Testing (C/Unity)**

Located in `unit_tests/`, these tests target individual C functions in total isolation.

- **Framework**: [Unity](https://github.com/ThrowTheSwitch/Unity).
- **Coverage Tooling**:
  - **Instrumentation**: Compiled with `gcc --coverage -fprofile-arcs -ftest-coverage`.
  - **Reporting**: `gcovr` is used to aggregate `.gcda` files and generate **Cobertura XML** for Jenkins and **HTML** for developers.
- **Test Cases**:
  - `test_brake_logic.c`: Boundary conditions for ABS (speed > 100km/h), sensor clamping for invalid inputs (0-100%), and warning flag logic for Overheat (>200°C) and Wear (>90%).
  - `test_schm.c`: Validates the internal tick counter and task triggering.
  - `test_can_stack.c`: Uses the **Mock Injection API** to verify that the BSW correctly processes incoming CAN data into internal variables.

#### **Layer B: Functional/HIL Testing (Python/Pytest)**

Located in `functional_tests/`, these tests treat the ECU as a black box.

- **Infrastructure**: Uses `python-can` and a **Virtual CAN Bus** (`vbus_shared`) to simulate the vehicle network.
- **Simulation**: A `VirtualECU` thread in `conftest.py` imitates the real-time behavior of the firmware.
- **Test Scenarios**:
  - **Fault Injection**: Mocking short-to-ground or open-circuit conditions to verify fail-safe behavior.
  - **Electrical Stress**: Simulating low-voltage (9V) or ignition cycle recovery using the `power_supply` fixture.
  - **DTC/UDS**: Simulating diagnostic sessions and status logging.

---

## 📂 Evolution of the Project Structure

We recently refactored the project to adopt a more professional naming convention:

```text
SWE6-Test/
├── unit_tests/           # C Unit Tests (The "Inside-the-box" logic)
│   ├── unity/            # Unity Framework source
│   ├── test_brake_logic.c
│   ├── test_schm.c
│   └── test_can_stack.c
├── functional_tests/     # Python HIL/Integration Tests (The "Outside-the-box" behavior)
│   ├── conftest.py       # Virtual ECU & HIL Fixtures
│   ├── __init__.py      # Package marker for discovery
│   └── test_*.py         # High-level requirement verification
├── src/                  # Production Firmware Source
├── scripts/              # CI/CD Helper Scripts (Mock flashers, ALM uploaders)
├── build/                # Compiled binaries and coverage artifacts
└── Jenkinsfile           # The "Source of Truth" for automation
```

---

## 🚀 The CI/CD Pipeline (`Jenkinsfile`)

The pipeline is designed for **Zero-Touch Automation**. Every commit triggers a full validation battery:

1.  **Stage: Setup**: Initializes a Python Virtual Environment (`.venv`) and installs `requirements.txt` (including `gcovr`, `pytest-cov`, and `allure-pytest`).
2.  **Stage: Build**: Compiles production firmware into `firmware.elf`.
3.  **Stage: Unit Tests (C)**: Uses `Make` to compile and run all Unity tests with coverage instrumentation.
4.  **Stage: Coverage (C)**: Invokes `gcovr` to generate `build/c-coverage.xml`.
5.  **Stage: Linting**: Runs `pylint` on Python scripts and tests to ensure code quality.
6.  **Stage: Quality Suite (Axivion Style)**: A professional static analysis suite that checks MISRA components, architecture layer violations, and generates a visual HTML compliance dashboard.
7.  **Stage: Functional Tests**: Executes the full `pytest` suite on the Virtual CAN bus.
8.  **Stage: Reporting**:
    - **JUnit**: Uploads `test-results.xml` for Jenkins dashboard.
    - **Allure**: Generates interactive visual historical reports.
    - **Coverage**: Archives `coverage.xml` (Python) and `c-coverage.xml` (C).

---

## 🛠️ Developer Manual (Boring but Essential)

### Running Everything Locally

To replicate the Jenkins environment on your workstation:

```bash
# 1. Prepare Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run C Unit Tests & Coverage
make clean
make test_c
gcovr -r . --filter src/ --html-details build/c-coverage.html

# 3. Run Python Functional Tests
pytest functional_tests/ --alluredir=allure-results
```

### Addressing "Detached HEAD" or Push Issues

If the pipeline fails after a rename/refactor, ensure:

1.  **Imports**: No static imports refer to the old `tests/` directory (use `functional_tests/`).
2.  ****init**.py**: Every test folder must have an `__init__.py` for package discovery.
3.  **Path Consistency**: The `Jenkinsfile` and `Makefile` must both have the same view of the filesystem.

---

## 📈 Future Outlook

- **Static Analysis (C)**: Integrate MISRA-C checkers (e.g., Cppcheck or PC-Lint).
- **Complex Scenarios**: Add multi-ECU coordination tests (e.g., Brake ECU + Steering ECU interaction).
- **Requirement Traceability**: Fully map every Python test to a specific requirement in `Polarion` via the result uploader.

---

**Maintained by**: Antigravity AI
**Status**: Fully Automated / SWE.6 & SWE.5 Compliant
