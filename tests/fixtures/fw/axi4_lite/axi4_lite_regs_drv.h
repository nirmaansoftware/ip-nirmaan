/*
 * axi4_lite_regs_drv.h: a driver for the axi4_lite_regs register block.
 *
 * The driver reaches the hardware only through a nirmaan_hal, so the same
 * code runs on a target and against the RTL under fw.test. Every call returns
 * a status; a bus error (SLVERR or DECERR from the block) is reported to the
 * caller, never swallowed, and the raw response is kept in last_response.
 */
#ifndef AXI4_LITE_REGS_DRV_H
#define AXI4_LITE_REGS_DRV_H

#include <stdint.h>

#include "nirmaan_hal.h"

#define AXIL_REGS_OK 0
#define AXIL_REGS_BUS_ERROR (-1)
#define AXIL_REGS_BAD_ARGUMENT (-2)

typedef struct axil_regs {
    const nirmaan_hal *hal;
    unsigned last_response; /* the response code of the latest bus transfer */
} axil_regs;

void axil_regs_init(axil_regs *dev, const nirmaan_hal *hal);

/* Register access by index, 0 to AXIL_REGS_COUNT - 1. */
int axil_regs_write(axil_regs *dev, unsigned index, uint32_t value);
int axil_regs_read(axil_regs *dev, unsigned index, uint32_t *value);

/* Write one byte lane (0 to 3) of a register, leaving the other bytes alone. */
int axil_regs_write_byte(axil_regs *dev, unsigned index, unsigned lane, uint8_t value);

/* Raw access at a byte offset, for diagnostics. An unmapped offset is a bus error. */
int axil_regs_write_offset(axil_regs *dev, uint32_t offset, uint32_t value);
int axil_regs_read_offset(axil_regs *dev, uint32_t offset, uint32_t *value);

#endif /* AXI4_LITE_REGS_DRV_H */
