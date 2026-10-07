/*
 * apb_regs_drv.h: a driver for the apb_regs register block.
 *
 * The driver reaches the hardware only through a nirmaan_hal, so the same
 * code runs on any core and bus. Every call returns a status; a bus error
 * (PSLVERR from the block, which the HAL reports as SLVERR) is reported to
 * the caller, never swallowed, and the raw response is kept in last_response.
 */
#ifndef APB_REGS_DRV_H
#define APB_REGS_DRV_H

#include <stdint.h>

#include "nirmaan_hal.h"

#define APB_REGS_OK 0
#define APB_REGS_BUS_ERROR (-1)
#define APB_REGS_BAD_ARGUMENT (-2)

typedef struct apb_regs {
    const nirmaan_hal *hal;
    unsigned last_response; /* the response code of the latest bus transfer */
} apb_regs;

void apb_regs_init(apb_regs *dev, const nirmaan_hal *hal);

/* Register access by index, 0 to APB_REGS_COUNT - 1. */
int apb_regs_write(apb_regs *dev, unsigned index, uint32_t value);
int apb_regs_read(apb_regs *dev, unsigned index, uint32_t *value);

/* Write one byte lane (0 to 3) of a register, leaving the other bytes alone. */
int apb_regs_write_byte(apb_regs *dev, unsigned index, unsigned lane, uint8_t value);

/* Raw access at a byte offset, for diagnostics. An unmapped offset is a bus error. */
int apb_regs_write_offset(apb_regs *dev, uint32_t offset, uint32_t value);
int apb_regs_read_offset(apb_regs *dev, uint32_t offset, uint32_t *value);

#endif /* APB_REGS_DRV_H */
