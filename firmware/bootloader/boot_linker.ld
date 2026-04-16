/* Linker script for STM32F401RE Bootloader (Sector 0) */
MEMORY
{
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 16K
    SRAM (rwx) : ORIGIN = 0x20000000, LENGTH = 96K
}

_estack = ORIGIN(SRAM) + LENGTH(SRAM);

SECTIONS
{
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } > FLASH

    .text :
    {
        . = ALIGN(4);
        *(.text)
        *(.text*)
        . = ALIGN(4);
    } > FLASH

    .data :
    {
        _sdata = .;
        *(.data)
        *(.data*)
        _edata = .;
    } > SRAM AT > FLASH

    .bss :
    {
        _sbss = .;
        *(.bss)
        *(.bss*)
        _ebss = .;
    } > SRAM
}
