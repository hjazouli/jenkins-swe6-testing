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

test_c: test_brake_logic test_schm test_can_stack

test_brake_logic:
	mkdir -p build/unit_tests
	$(CC) $(CFLAGS) --coverage -Iunit_tests/unity unit_tests/unity/unity.c src/app/brake_logic.c unit_tests/test_brake_logic.c -o build/unit_tests/test_brake_logic
	./build/unit_tests/test_brake_logic

test_schm:
	mkdir -p build/unit_tests
	$(CC) $(CFLAGS) --coverage -Iunit_tests/unity unit_tests/unity/unity.c src/bsw/schm.c unit_tests/test_schm.c -o build/unit_tests/test_schm
	./build/unit_tests/test_schm

test_can_stack:
	mkdir -p build/unit_tests
	$(CC) $(CFLAGS) --coverage -Iunit_tests/unity unit_tests/unity/unity.c src/bsw/can_stack.c unit_tests/test_can_stack.c -o build/unit_tests/test_can_stack
	./build/unit_tests/test_can_stack

test_bcm:
	mkdir -p build/bcm_tests
	$(CC) $(CFLAGS) -Ibcm/include -Iunit_tests/unity \
	unit_tests/unity/unity.c \
	bcm/src/*.c \
	bcm/test/test_bcm.c \
	-o build/bcm_tests/test_bcm
	./build/bcm_tests/test_bcm

# Launch the Jenkins dashboard easily
jenkins:
	./scripts/launch_jenkins.sh

.PHONY: all clean test_c test_brake_logic test_schm test_can_stack jenkins test_bcm
