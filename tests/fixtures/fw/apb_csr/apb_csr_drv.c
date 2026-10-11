/*
 * apb_csr_drv.c: a driver for the apb_csr control and status registers.
 */
#include "apb_csr_drv.h"

#include <stddef.h>

#include "apb_csr_map.h"

static int status_of(apb_csr *dev, unsigned response) {
    dev->last_response = response;
    return response == NIRMAAN_BUS_OKAY ? APB_CSR_OK : APB_CSR_BUS_ERROR;
}

static int read_reg(apb_csr *dev, uint32_t offset, uint32_t *value) {
    if (dev == NULL || dev->hal == NULL || value == NULL) {
        return APB_CSR_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->read32(dev->hal->ctx, offset, value));
}

static int write_reg(apb_csr *dev, uint32_t offset, uint32_t value) {
    if (dev == NULL || dev->hal == NULL) {
        return APB_CSR_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->write32(dev->hal->ctx, offset, value, 0xFu));
}

void apb_csr_init(apb_csr *dev, const nirmaan_hal *hal) {
    dev->hal = hal;
    dev->last_response = NIRMAAN_BUS_OKAY;
}

int apb_csr_set_mode(apb_csr *dev, unsigned mode) {
    uint32_t ctrl = 0u;
    int status;
    if (mode > (APB_CSR_CTRL_MODE_MASK >> APB_CSR_CTRL_MODE_SHIFT)) {
        return APB_CSR_BAD_ARGUMENT;
    }
    status = read_reg(dev, APB_CSR_CTRL_OFFSET, &ctrl);
    if (status != APB_CSR_OK) {
        return status;
    }
    return write_reg(dev, APB_CSR_CTRL_OFFSET, APB_CSR_CTRL_MODE_SET(ctrl, mode));
}

int apb_csr_mode(apb_csr *dev, unsigned *mode) {
    uint32_t ctrl = 0u;
    int status;
    if (mode == NULL) {
        return APB_CSR_BAD_ARGUMENT;
    }
    status = read_reg(dev, APB_CSR_CTRL_OFFSET, &ctrl);
    *mode = (unsigned)APB_CSR_CTRL_MODE_GET(ctrl);
    return status;
}

int apb_csr_enable(apb_csr *dev, int on) {
    uint32_t ctrl = 0u;
    int status = read_reg(dev, APB_CSR_CTRL_OFFSET, &ctrl);
    if (status != APB_CSR_OK) {
        return status;
    }
    return write_reg(dev, APB_CSR_CTRL_OFFSET, APB_CSR_CTRL_ENABLE_SET(ctrl, on ? 1u : 0u));
}

int apb_csr_reset_seen(apb_csr *dev, int *seen) {
    uint32_t value = 0u;
    int status;
    if (seen == NULL) {
        return APB_CSR_BAD_ARGUMENT;
    }
    status = read_reg(dev, APB_CSR_STATUS_OFFSET, &value);
    *seen = APB_CSR_STATUS_RESET_DONE_GET(value) != 0u;
    return status;
}

int apb_csr_ack_reset(apb_csr *dev) {
    /* Write-1-to-clear: only RESET_DONE is written as 1; VERSION is read-only. */
    return write_reg(dev, APB_CSR_STATUS_OFFSET, APB_CSR_STATUS_RESET_DONE_MASK);
}

int apb_csr_version(apb_csr *dev, unsigned *version) {
    uint32_t value = 0u;
    int status;
    if (version == NULL) {
        return APB_CSR_BAD_ARGUMENT;
    }
    status = read_reg(dev, APB_CSR_STATUS_OFFSET, &value);
    *version = (unsigned)APB_CSR_STATUS_VERSION_GET(value);
    return status;
}

int apb_csr_id(apb_csr *dev, uint32_t *id) {
    return read_reg(dev, APB_CSR_ID_OFFSET, id);
}
