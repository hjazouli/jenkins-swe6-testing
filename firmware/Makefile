# Toolchain
CC = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy

# Paths
BCM_PATH = ../bcm
FIRMWARE_PATH = .

# Includes
INCLUDES = -I$(FIRMWARE_PATH)/src \
           -I$(FIRMWARE_PATH)/drivers \
           -I$(FIRMWARE_PATH)/drivers/cmsis \
           -I$(BCM_PATH)/include \
           -I$(BCM_PATH)/src

# Versioning
GIT_VERSION = $(shell git describe --tags --always --dirty)

# Options
CFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -O0 -g $(INCLUDES)
CFLAGS += -DBCM_SW_VERSION=\"$(GIT_VERSION)\" -DSTM32F401xE -DUSE_FULL_LL_DRIVER
LDFLAGS = -T linker.ld -nostdlib

# Sources
SRCS = src/startup_stm32f401re.s \
       src/main.c \
       $(BCM_PATH)/src/bcm_core.c \
       $(BCM_PATH)/src/bcm_safety.c \
       $(BCM_PATH)/src/bcm_ebd.c \
       $(BCM_PATH)/src/bcm_abs.c \
       $(BCM_PATH)/src/bcm_diag.c \
       $(BCM_PATH)/src/bcm_hsa.c \
       $(BCM_PATH)/src/bcm_hwmon.c \
       $(BCM_PATH)/src/bcm_regen.c

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
