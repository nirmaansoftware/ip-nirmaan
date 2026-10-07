/* irq_picorv32.S: PicoRV32's part of the interrupt runtime (docs/RISCV_NEXT.md, section 2).
 *
 * The design's line is PicoRV32's irq[3]. The core enters the vector at 0x10
 * with the return address in q0, and returns with retirq; maskirq sets the
 * mask (a set bit masks). These are PicoRV32's own instructions, emitted with
 * .insn (opcode custom-0); their encodings are in PicoRV32's README. Reset
 * leaves every line masked, and lines 0 to 2 (the core's timer, ebreak, and
 * misalignment) stay masked, so those still trap through the core's trap
 * output. */
#define LINE_MASKED 0xffffffff   /* every line masked */
#define LINE_ENABLED 0xfffffff7  /* every line masked but irq[3] */

    .text

/* void nirmaan_core_init(void): nothing to set up; the line stays masked until attached. */
    .globl nirmaan_core_init
nirmaan_core_init:
    ret

/* unsigned nirmaan_core_irq_set(unsigned on): enable (1) or mask (0) the design's line; return the previous setting. */
    .globl nirmaan_core_irq_set
nirmaan_core_irq_set:
    li t0, LINE_MASKED
    beqz a0, 1f
    li t0, LINE_ENABLED
1:  .insn r 0x0B, 6, 3, a1, t0, zero  /* maskirq a1, t0: a1 is the previous mask */
    srli a1, a1, 3
    andi a1, a1, 1
    xori a0, a1, 1
    ret

/* The entry from the vector: save the caller-saved registers on the interrupted stack, dispatch, restore, retirq. */
    .globl nirmaan_core_trap
nirmaan_core_trap:
    addi sp, sp, -64
    sw ra, 0(sp)
    sw t0, 4(sp)
    sw t1, 8(sp)
    sw t2, 12(sp)
    sw a0, 16(sp)
    sw a1, 20(sp)
    sw a2, 24(sp)
    sw a3, 28(sp)
    sw a4, 32(sp)
    sw a5, 36(sp)
    sw a6, 40(sp)
    sw a7, 44(sp)
    sw t3, 48(sp)
    sw t4, 52(sp)
    sw t5, 56(sp)
    sw t6, 60(sp)
    call nirmaan_irq_dispatch
    lw ra, 0(sp)
    lw t0, 4(sp)
    lw t1, 8(sp)
    lw t2, 12(sp)
    lw a0, 16(sp)
    lw a1, 20(sp)
    lw a2, 24(sp)
    lw a3, 28(sp)
    lw a4, 32(sp)
    lw a5, 36(sp)
    lw a6, 40(sp)
    lw a7, 44(sp)
    lw t3, 48(sp)
    lw t4, 52(sp)
    lw t5, 56(sp)
    lw t6, 60(sp)
    addi sp, sp, 64
    .insn r 0x0B, 0, 2, zero, zero, zero  /* retirq: return to q0 */
