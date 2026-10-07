/* crt0.S: reset entry and trap vector for the firmware image.
 *
 * 0x00  reset: jump over the vector
 * 0x10  the trap vector: every core enters its interrupt (and, on SERV, its
 *       exception) handler here; nirmaan_core_trap is in the core's runtime
 *       file, irq_<core>.S (docs/RISCV_NEXT.md, section 2)
 *
 * Reset sets the global and stack pointers, clears .bss, lets the core's
 * runtime set up its interrupts (still disabled), runs the tests, and parks
 * if main ever returns. */
    .section .text.start, "ax"
    .option push
    .option norelax
    .globl _start
_start:
    j reset
    .balign 16
    .globl nirmaan_trap_vector
nirmaan_trap_vector:
    j nirmaan_core_trap
reset:
    la gp, __global_pointer$
    .option pop
    la sp, __stack_top
    la t0, __bss_start
    la t1, __bss_end
1:  bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b
2:  call nirmaan_core_init
    call nirmaan_soc_main
3:  j 3b
