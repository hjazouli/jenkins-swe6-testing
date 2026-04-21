/*
 * startup_stm32f401re.s
 * Standard ARM Startup for STM32F401RE 
 */

.syntax unified
.cpu cortex-m4
.fpu softvfp
.thumb

.global g_pfnVectors
.global Default_Handler

/* End of Stack address (Defined in Linker Script) */
.word _sstatus
/* Start of Data (Defined in Linker Script) */
.word _sdata
.word _edata
.word _sidata
/* BSS (Defined in Linker Script) */
.word _sbss
.word _ebss

.section .text.Reset_Handler
.weak Reset_Handler
.type Reset_Handler, %function

Reset_Handler:
  /* 1. Setup Stack Pointer */
  ldr   sp, =_estack

  /* 2. Copy .data section from FLASH to RAM */
  ldr   r0, =_sdata
  ldr   r1, =_edata
  ldr   r2, =_sidata
  movs  r3, #0
  b     LoopCopyDataInit

CopyDataInit:
  ldr   r4, [r2, r3]
  str   r4, [r0, r3]
  adds  r3, r3, #4

LoopCopyDataInit:
  adds  r4, r0, r3
  cmp   r4, r1
  bcc   CopyDataInit

  /* 3. Zero-fill .bss section (RAM initialization) */
  ldr   r2, =_sbss
  ldr   r4, =_ebss
  movs  r3, #0
  b     LoopFillZerobss

FillZerobss:
  str   r3, [r2]
  adds  r2, r2, #4

LoopFillZerobss:
  cmp   r2, r4
  bcc   FillZerobss

  /* 4. Enable FPU (Coprocessor 10 and 11) */
  ldr     r0, =0xE000ED88
  ldr     r1, [r0]
  orr     r1, r1, #(0xF << 20)
  str     r1, [r0]
  dsb
  isb

  /* 5. Call the application's entry point */
  bl    main

LoopForever:
  b     LoopForever

.size Reset_Handler, .-Reset_Handler

/* Vector Table */
.section .isr_vector,"a",%progbits
.type g_pfnVectors, %object

g_pfnVectors:
  .word _estack
  .word Reset_Handler
  .word Default_Handler /* NMI */
  .word Default_Handler /* HardFault */
  /* Add more handlers as needed ... */

.size g_pfnVectors, .-g_pfnVectors

.section .text.Default_Handler,"ax",%progbits
Default_Handler:
Infinite_Loop:
  b Infinite_Loop
.size Default_Handler, .-Default_Handler
