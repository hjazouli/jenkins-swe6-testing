# Makefile for Layered Mock ECU Firmware (ASW/BSW)

CC = gcc
CFLAGS = -Wall -Isrc
TARGET = build/firmware.elf

# List all source files in the project
SRCS = src/main.c \
       src/app/brake_logic.c \
       src/bsw/can_stack.c \
       src/bsw/schm.c

# Generate object file paths
OBJS = $(SRCS:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	mkdir -p build
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf build/
	rm -f $(OBJS)

test_unit:
	mkdir -p build/unit_tests
	$(CC) $(CFLAGS) -Ibcm/include -Itests/unit/unity \
	tests/unit/unity/unity.c \
	bcm/src/*.c \
	tests/unit/test_bcm_core.c \
	-o build/unit_tests/test_bcm_core
	./build/unit_tests/test_bcm_core

# Launch the Jenkins dashboard easily
jenkins:
	./scripts/launch_jenkins.sh

test_hil:
	./.venv/bin/pytest tests/functional

.PHONY: all clean test_unit jenkins test_hil

