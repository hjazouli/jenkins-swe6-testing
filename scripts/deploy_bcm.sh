#!/bin/bash
set -e

# New Hardened Infrastructure Deployment Script
# ---------------------------------------------
# Path to the CubeMX-generated project
FIRMWARE_DIR="firmware/BCM_Firmware"
BINARY_PATH="$FIRMWARE_DIR/build/BCM_Firmware.bin"

echo "🔨 --- COMPILING HARDENED BCM FIRMWARE ---"
make -C $FIRMWARE_DIR clean all

echo "⚡ --- FLASHING FIRMWARE TO 0x08000000 ---"
# We now flash to the base address (0x08000000) as the bootloader is retired
st-flash write $BINARY_PATH 0x08000000

echo "🔄 --- RESETTING BOARD ---"
st-flash reset

echo "✅ --- DEPLOYMENT SUCCESSFUL ---"
echo "Note: Firmware running at 115,200 Baud / 84 MHz."
