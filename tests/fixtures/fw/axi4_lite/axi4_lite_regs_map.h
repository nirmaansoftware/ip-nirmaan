/*
 * axi4_lite_regs_map.h: the register map of axi4_lite_regs, from the approved
 * interface specification (section 3, "Register map"; section 5, responses).
 */
#ifndef AXI4_LITE_REGS_MAP_H
#define AXI4_LITE_REGS_MAP_H

#define AXIL_REGS_COUNT 4u

/* Byte offsets. Every register is 32 bits, read/write, and resets to zero. */
#define AXIL_REGS_REG0_OFFSET 0x0u
#define AXIL_REGS_REG1_OFFSET 0x4u
#define AXIL_REGS_REG2_OFFSET 0x8u
#define AXIL_REGS_REG3_OFFSET 0xCu

#define AXIL_REGS_RESET_VALUE 0x00000000u

/* The offsets under the names the approved register map generates (M44: the driver
 * is built with the map in the end-to-end project, which checks these). */
#define AXI4_LITE_REGS_REG0_OFFSET 0x0u
#define AXI4_LITE_REGS_REG1_OFFSET 0x4u
#define AXI4_LITE_REGS_REG2_OFFSET 0x8u
#define AXI4_LITE_REGS_REG3_OFFSET 0xCu

#endif /* AXI4_LITE_REGS_MAP_H */
