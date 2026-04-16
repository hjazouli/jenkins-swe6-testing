# Toolchain
CC = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy

# Options
CFLAGS = -mcpu=cortex-m4 -mthumb -O0 -g
LDFLAGS = -T boot_linker.ld -nostdlib

# Targets
all: bootloader.bin

bootloader.elf: src/boot_main.c
	$(CC) $(CFLAGS) $(LDFLAGS) src/boot_main.c -o bootloader.elf

bootloader.bin: bootloader.elf
	$(OBJCOPY) -O binary bootloader.elf bootloader.bin

flash: bootloader.bin
	st-flash write bootloader.bin 0x08000000

clean:
	rm -f *.elf *.bin
