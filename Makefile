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

.PHONY: all clean
