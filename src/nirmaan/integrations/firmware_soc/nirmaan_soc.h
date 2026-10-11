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

/* Bus errors as traps (docs/FIRMWARE_IRQ_TRAPS.md, section 4). */
#define NIRMAAN_SOC_BERR_CTRL (*(volatile uint32_t *)0x20000010u) /* bit 0 TRAP; bit 1 WIRED (read only) */
#define NIRMAAN_SOC_BERR_INFO (*(volatile uint32_t *)0x20000014u) /* bit 0 PENDING (W1C), 1 WRITE, 3:2 response */
#define NIRMAAN_SOC_BERR_ADDR (*(volatile uint32_t *)0x20000018u) /* the faulting access's bus offset */
#define NIRMAAN_SOC_BERR_TRAP 0x1u
#define NIRMAAN_SOC_BERR_WIRED 0x2u
#define NIRMAAN_SOC_BERR_PENDING 0x1u
#define NIRMAAN_SOC_BERR_WRITE 0x2u

/* The core's part of the runtime, in irq_<core>.S (docs/RISCV_NEXT.md, section 2). */
void nirmaan_core_init(void);                 /* called by crt0.S before the tests; interrupts stay off */
unsigned nirmaan_core_irq_set(unsigned on);   /* enable (1) or disable (0) the design's line; returns the old setting */
int nirmaan_core_bus_error_set(unsigned on);  /* enable (1) or disable (0) the bus-error trap; 0 if the core has none */

/* Called by the core's trap entry: an interrupt, or (on a core that traps through the vector) an exception. */
void nirmaan_irq_dispatch(void);
void nirmaan_bus_fault_dispatch(uint32_t pc); /* a bus-error trap; pc is the faulting load or store */
void nirmaan_soc_trapped(uint32_t cause, uint32_t pc);

#endif /* NIRMAAN_SOC_H */
