/*
 * apb_csr_drv.h: a driver for the apb_csr control and status registers.
 *
 * The register header, apb_csr_map.h, is not written here: the firmware
 * tools generate it from the approved register map (offsets, resets, field
 * masks, and the _GET and _SET field accessors). Every call returns a status;
 * a bus error is reported to the caller, never swallowed.
 */
#ifndef APB_CSR_DRV_H
#define APB_CSR_DRV_H

#include <stdint.h>

#include "nirmaan_hal.h"

#define APB_CSR_OK 0
#define APB_CSR_BUS_ERROR (-1)
#define APB_CSR_BAD_ARGUMENT (-2)

typedef struct apb_csr {
    const nirmaan_hal *hal;
    unsigned last_response; /* the response code of the latest bus transfer */
} apb_csr;

void apb_csr_init(apb_csr *dev, const nirmaan_hal *hal);

/* CTRL.MODE (0 to 7) and CTRL.ENABLE, each changed without touching the other. */
int apb_csr_set_mode(apb_csr *dev, unsigned mode);
int apb_csr_mode(apb_csr *dev, unsigned *mode);
int apb_csr_enable(apb_csr *dev, int on);

/* STATUS.RESET_DONE: set by reset; acknowledged by writing 1 to it. */
int apb_csr_reset_seen(apb_csr *dev, int *seen);
int apb_csr_ack_reset(apb_csr *dev);

/* STATUS.VERSION and the ID register. */
int apb_csr_version(apb_csr *dev, unsigned *version);
int apb_csr_id(apb_csr *dev, uint32_t *id);

#endif /* APB_CSR_DRV_H */
