/*
 * nirmaan_soc.h: the memory map of nirmaan_soc.v, as the firmware sees it.
 * See docs/RISCV_FIRMWARE.md, section 3.
 */
#ifndef NIRMAAN_SOC_H
#define NIRMAAN_SOC_H

#include <stdint.h>

/* The design under test, with a register shift of 2: AXI byte offset N is the word at DEVICE + 4 * N. */
#define NIRMAAN_SOC_DEVICE 0x10000000u
#define NIRMAAN_SOC_DEVICE_SHIFT 2u

/* SoC control registers. */
#define NIRMAAN_SOC_STATUS (*(volatile uint32_t *)0x20000000u)  /* read: the latest device response */
#define NIRMAAN_SOC_CONSOLE (*(volatile uint32_t *)0x20000004u) /* write: one character */
#define NIRMAAN_SOC_EXIT (*(volatile uint32_t *)0x20000008u)    /* write: end the run with this code */
#define NIRMAAN_SOC_CYCLES (*(volatile uint32_t *)0x2000000Cu)  /* read: cycles since reset */

#endif /* NIRMAAN_SOC_H */
