#!/bin/bash

# 1. Build and Flash the Application (The BCM logic) at 0x08004000
echo "--- Compiling Application ---"
cd /Users/hichamjazouli/Gravity/SWE6-Test/firmware
make clean && make all
echo "--- Flashing Application to 0x08004000 ---"
st-flash write blinky.bin 0x08004000

# 2. Build and Flash the Bootloader at 0x08000000
echo "--- Compiling Bootloader ---"
cd /Users/hichamjazouli/Gravity/SWE6-Test/firmware/bootloader
make clean && make all
echo "--- Flashing Bootloader to 0x08000000 ---"
st-flash write bootloader.bin 0x08000000

echo "--- DEPLOYMENT COMPLETE ---"
echo "Instructions:"
echo "1. Normal Reboot: Board should Blink (Application running)."
echo "2. Hold BLUE BUTTON + Reset: LED stays SOLID (Bootloader Mode)."
