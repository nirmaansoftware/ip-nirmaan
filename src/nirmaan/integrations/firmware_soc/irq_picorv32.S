/* irq_picorv32.S: PicoRV32's part of the interrupt runtime (docs/RISCV_NEXT.md, section 2).
 *
 * The design's line is PicoRV32's irq[3], and the SoC's bus-error line is
 * irq[4] (docs/FIRMWARE_IRQ_TRAPS.md, section 4). The core enters the vector
 * at 0x10 with the return address in q0 and the lines it is taking in q1, and
 * returns with retirq; maskirq sets the mask (a set bit masks) and getq reads
 * a q register. These are PicoRV32's own instructions, emitted with .insn
 * (opcode custom-0); their encodings are in PicoRV32's README. Reset leaves
 * every line masked, and lines 0 to 2 (the core's timer, ebreak, and
 * misalignment) stay masked, so those still trap through the core's trap
 * output. Each of irq[3] and irq[4] is unmasked and masked on its own. */
#define LINE_DEVICE 8      /* irq[3] */
#define LINE_BUS_ERROR 16  /* irq[4] */

    .text

/* void nirmaan_core_init(void): nothing to set up; the lines stay masked until attached. */
    .globl nirmaan_core_init
nirmaan_core_init:
    ret

/* Set (a0 = 0) or clear (a0 != 0) the mask bit a2, leaving the others; return 1 if it was clear before.
 * Every line is masked between the two maskirq, so nothing can be taken while the mask is rebuilt. */
set_line:
    li t0, -1
    .insn r 0x0B, 6, 3, a1, t0, zero  /* maskirq a1, t0: mask everything; a1 is the previous mask */
    or t1, a1, a2
    beqz a0, 1f
    not t2, a2
    and t1, a1, t2
1:  .insn r 0x0B, 6, 3, zero, t1, zero  /* maskirq zero, t1 */
    and a1, a1, a2
    seqz a0, a1
    ret

/* unsigned nirmaan_core_irq_set(unsigned on): enable (1) or mask (0) the design's line; return the previous setting. */
    .globl nirmaan_core_irq_set
nirmaan_core_irq_set:
    li a2, LINE_DEVICE
    j set_line

/* int nirmaan_core_bus_error_set(unsigned on): enable (1) or mask (0) the bus-error line; returns 1 (supported). */
    .globl nirmaan_core_bus_error_set
nirmaan_core_bus_error_set:
    li a2, LINE_BUS_ERROR
    addi sp, sp, -16
    sw ra, 0(sp)
    call set_line
    lw ra, 0(sp)
    addi sp, sp, 16
    li a0, 1
    ret

/* The entry from the vector: save the caller-saved registers on the interrupted stack; dispatch a bus error
 * first (with the faulting instruction's address, q0 - 4: RV32I has no compressed instructions here), then
 * the design's interrupt; restore; retirq. */
    .globl nirmaan_core_trap
nirmaan_core_trap:
    addi sp, sp, -80
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
    .insn r 0x0B, 4, 0, t0, x1, zero  /* getq t0, q1: the lines being taken */
    sw t0, 64(sp)
    andi t0, t0, LINE_BUS_ERROR
    beqz t0, 1f
    .insn r 0x0B, 4, 0, a0, x0, zero  /* getq a0, q0: the next instruction */
    andi a0, a0, -2
    addi a0, a0, -4
    call nirmaan_bus_fault_dispatch
1:  lw t0, 64(sp)
    andi t0, t0, LINE_DEVICE
    beqz t0, 2f
    call nirmaan_irq_dispatch
2:  lw ra, 0(sp)
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
    addi sp, sp, 80
    .insn r 0x0B, 0, 2, zero, zero, zero  /* retirq: return to q0 */
