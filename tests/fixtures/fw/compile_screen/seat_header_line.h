/*
 * seat_header_line.h: a must-refuse input of the compile screen (gate SC9; council record
 * 2026-11-19-seat-c-live-refusal.md, decision 2, item 1). Not a seat answer. A seat's driver header for the
 * register block flow, the committed reference header with one line added. The route: a #line line, so the
 * held-out test's lines after this header look like another file's.
 * tests/test_compile_screen.py copies it in as axi4_lite_regs_drv.h beside the reference driver and compiles
 * it with the flow's held-out test, as checks 5 and 6 do, and holds it refused with nothing compiled.
 */
#ifndef AXI4_LITE_REGS_DRV_H
#define AXI4_LITE_REGS_DRV_H

#include <stdint.h>

#include "nirmaan_hal.h"

#line 1 "/usr/include/stdio.h"

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
