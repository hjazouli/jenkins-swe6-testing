# Makefile for Mock ECU Firmware

CC = gcc
CFLAGS = -Wall
TARGET = build/firmware.elf

all: $(TARGET)

$(TARGET): src/main.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $(TARGET) src/main.c

clean:
	rm -rf build/
