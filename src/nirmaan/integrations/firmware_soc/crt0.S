/* crt0.S: reset entry for the firmware image. Set the global and stack
 * pointers, clear .bss, run the tests, and park if main ever returns. */
    .section .text.start, "ax"
    .globl _start
_start:
    .option push
    .option norelax
    la gp, __global_pointer$
    .option pop
    la sp, __stack_top
    la t0, __bss_start
    la t1, __bss_end
1:  bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b
2:  call nirmaan_soc_main
3:  j 3b
