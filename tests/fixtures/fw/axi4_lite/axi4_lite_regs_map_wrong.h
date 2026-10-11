/*
 * axi4_lite_regs_map.h, DELIBERATELY WRONG: REG2 is given REG1's offset (a
 * copy and paste slip). It compiles cleanly under the strict flags; only a
 * run against the real RTL shows that writing REG2 overwrites REG1. The M25
 * tests submit it under the correct file name to prove fw.test catches it.
 */
#ifndef AXI4_LITE_REGS_MAP_H
#define AXI4_LITE_REGS_MAP_H

#define AXIL_REGS_COUNT 4u

/* Byte offsets. Every register is 32 bits, read/write, and resets to zero. */
#define AXIL_REGS_REG0_OFFSET 0x0u
#define AXIL_REGS_REG1_OFFSET 0x4u
#define AXIL_REGS_REG2_OFFSET 0x4u
#define AXIL_REGS_REG3_OFFSET 0xCu

#define AXIL_REGS_RESET_VALUE 0x00000000u

#endif /* AXI4_LITE_REGS_MAP_H */
