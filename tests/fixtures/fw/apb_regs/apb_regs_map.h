/*
 * apb_regs_map.h: the register map of apb_regs, from the approved
 * interface specification (section 3, "Register map"; section 5, responses).
 */
#ifndef APB_REGS_MAP_H
#define APB_REGS_MAP_H

#define APB_REGS_COUNT 4u

/* Byte offsets. Every register is 32 bits, read/write, and resets to zero. */
#define APB_REGS_REG0_OFFSET 0x0u
#define APB_REGS_REG1_OFFSET 0x4u
#define APB_REGS_REG2_OFFSET 0x8u
#define APB_REGS_REG3_OFFSET 0xCu

#define APB_REGS_RESET_VALUE 0x00000000u

#endif /* APB_REGS_MAP_H */
