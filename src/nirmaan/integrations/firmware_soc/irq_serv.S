/* irq_serv.S: SERV's part of the interrupt runtime (docs/RISCV_NEXT.md, section 2).
 *
 * SERV has the standard machine-mode CSRs it needs: mtvec, mepc, mcause,
 * mstatus.MIE, and mie.MTIE. Its one interrupt input, i_timer_irq, carries the
 * design's line (mcause 0x80000007). mtvec points at the vector at 0x10, which
 * also receives SERV's exceptions (a misaligned access, ecall, ebreak): those
 * end the run as a reported trap. */
    .text

/* void nirmaan_core_init(void): point mtvec at the vector and enable SERV's one line in mie;
 * mstatus.MIE stays clear until a handler is attached. */
    .globl nirmaan_core_init
nirmaan_core_init:
    la t0, nirmaan_trap_vector
    csrw mtvec, t0
    li t0, 0x80
    csrs mie, t0
    ret

/* unsigned nirmaan_core_irq_set(unsigned on): set (1) or clear (0) mstatus.MIE; return the previous setting. */
    .globl nirmaan_core_irq_set
nirmaan_core_irq_set:
    csrr a1, mstatus
    srli a1, a1, 3
    andi a1, a1, 1
    beqz a0, 1f
    csrsi mstatus, 8
    j 2f
1:  csrci mstatus, 8
2:  mv a0, a1
    ret

/* The entry from the vector: save the caller-saved registers on the interrupted stack; an interrupt
 * (mcause bit 31) is dispatched and returns with mret, an exception is reported and ends the run. */
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
    csrr a0, mcause
    bltz a0, 1f
    csrr a1, mepc
    call nirmaan_soc_trapped
1:  call nirmaan_irq_dispatch
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
    mret
