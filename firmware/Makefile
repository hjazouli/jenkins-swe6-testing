# Toolchain
CC = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy

# Paths
BCM_PATH = ../bcm
FIRMWARE_PATH = .

# Includes
INCLUDES = -I$(FIRMWARE_PATH)/src \
           -I$(BCM_PATH)/include \
           -I$(BCM_PATH)/src

# Options
CFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -O0 -g $(INCLUDES)
LDFLAGS = -T linker.ld -nostdlib

# Sources
SRCS = src/main.c \
       $(BCM_PATH)/src/bcm_safety.c

# Targets
all: blinky.bin

blinky.elf: $(SRCS)
	$(CC) $(CFLAGS) $(LDFLAGS) $(SRCS) -o blinky.elf

blinky.bin: blinky.elf
	$(OBJCOPY) -O binary blinky.elf blinky.bin

flash: blinky.bin
	st-flash write blinky.bin 0x08004000

clean:
	rm -f *.elf *.bin
