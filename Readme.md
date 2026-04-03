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
- **Out-of-Bounds Rejection (SWE_REQ_003)**: Verifies the virtual ECU safety logic clamping invalid pedal input (>100%) to a maximum of 100% prior to hydraulic calculation. 
- **Emergency Brake Assist (SWE_REQ_004)**: Verifies the simulated ECU handles instantaneous extreme forces (100% force in a single frame) safely.

### 4. Integration Tooling (`scripts/`)

- **Flashing Simulation**: `mock_lauterbach.py` imitates the behavior of industry-standard debuggers.
- **ALM Integration**: `polarion_upload.py` demonstrates how test results are integrated back into ALM (Application Lifecycle Management) tools for traceability.

## 📈 Summary of Technologies

- **Languages**: C, Python
- **Build System**: Make/GCC
- **CI/CD**: Jenkins (Locally Hosted)
- **Testing**: Pytest, python-can
- **Reporting**: JUnit, HTML (pytest-html)
- **Target**: Infineon TriCore TC397 (Mocked)

## 🔄 CI/CD Automation Setup (SCM Polling)

The Jenkins pipeline is designed to act seamlessly like **GitHub Actions**. It automatically detects source code changes pushed to the repository and isolated test builds are triggered natively.

**Architecture Breakdown & Why It Works:**
Previously, the integration relied on "GitHub Webhooks" alongside fragile SSH tunneling (e.g., `localhost.run`). Because local development laptops sit behind firewalls seamlessly routing incoming GitHub webhooks is inherently buggy. 

To solve this, the pipeline has been modified to use **SCM Polling**. 
- **Trigger Strategy:** The `Jenkinsfile` utilizes the trigger `pollSCM('* * * * *')`.
- **How it functions:** Every 60 seconds, the local Jenkins application makes an *outbound* HTTP connection to GitHub to inspect if the git history has progressed. If a new commit hash is detected, a build is initialized directly. This entirely bypasses firewall restrictions and requires *zero internet tunneling*.

**Instructions for the Next Developer:**
1. **Starting Jenkins Engine**: Simply spin up the local Jenkins footprint either via Docker (`docker-compose up -d`) or via the direct JAR artifact (`java -jar jenkins.war`). 
2. **Accessing Dashboard**: Navigate to `http://localhost:8081` on your local machine to monitor health metrics, view console outputs, or check pipeline status.
3. **Triggering the Build Pipeline**: You do not need to intervene manually! Write code, assert your logic, commit, and `git push origin main`. Within 60 seconds, Jenkins will independently intercept the repo state and execute the pipeline workflow.
4. **Altering Jenkins Configuration**: If making adjustments to the overarching CI workflow (e.g. adding code linting phases or modifying Jenkins architecture), alter the `Jenkinsfile` file directly. Upon pushing your modified `Jenkinsfile`, remember you must click "Build Now" manually from the Jenkins UI *exactly one time*. This informs Jenkins to resync its underlying triggers with your new script configuration.
