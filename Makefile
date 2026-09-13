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

BCM_SRCS = $(wildcard bcm/src/*.c)

test_unit:
	mkdir -p build/unit_tests
	$(CC) $(CFLAGS) -Ibcm/include -Itests/unit/unity \
	tests/unit/unity/unity.c \
	$(BCM_SRCS) \
	tests/unit/test_bcm_core.c \
	-o build/unit_tests/test_bcm_core
	./build/unit_tests/test_bcm_core

# System cc is Apple clang on macOS (no real `gcov`), so gcovr needs the
# llvm-cov shim there; anywhere a real `gcov` is on PATH (Linux, or gcc
# installed via brew), use that instead. --coverage's .gcno/.gcda files land
# in the CWD (repo root) since this doesn't build via separate -c/.o steps.
GCOV_EXE := $(shell command -v gcov 2>/dev/null)
ifeq ($(GCOV_EXE),)
GCOVR_GCOV_ARGS = --gcov-executable "xcrun llvm-cov gcov"
else
GCOVR_GCOV_ARGS =
endif

test_unit_coverage:
	mkdir -p build/unit_tests
	$(CC) $(CFLAGS) -Ibcm/include -Itests/unit/unity --coverage \
	tests/unit/unity/unity.c \
	$(BCM_SRCS) \
	tests/unit/test_bcm_core.c \
	-o build/unit_tests/test_bcm_core_cov
	./build/unit_tests/test_bcm_core_cov
	gcovr $(GCOVR_GCOV_ARGS) -r . --filter 'bcm/src/' --xml-pretty -o build/c-coverage.xml
	gcovr $(GCOVR_GCOV_ARGS) -r . --filter 'bcm/src/' --html-details -o build/c-coverage.html
	rm -f *.gcno *.gcda

# Launch the Jenkins dashboard easily
jenkins:
	./scripts/launch_jenkins.sh

test_hil:
	./.venv/bin/pytest tests/functional

.PHONY: all clean test_unit test_unit_coverage jenkins test_hil

