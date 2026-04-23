# BCM Project Makefile (GitLab & Jenkins Shared)
CC = gcc
CFLAGS = -Wall -Isrc -I../include -g
SRC_DIR = src
TEST_DIR = test
BUILD_DIR = build
UNITY_DIR = ../unit_tests/unity

# Source files
SRCS = $(wildcard $(SRC_DIR)/*.c)
TEST_SRCS = $(TEST_DIR)/test_bcm.c $(UNITY_DIR)/unity.c

# Phony targets
.PHONY: all compile test clean

all: compile test

compile:
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(SRCS)
	@echo "Build Successful"

test:
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SRCS) $(TEST_SRCS) -o $(BUILD_DIR)/unit_test
	./$(BUILD_DIR)/unit_test

clean:
	rm -rf $(BUILD_DIR)
