/*
 * apb_csr_test.c: driver-level tests for apb_csr, run by fw.test against the
 * RTL. Expected values come from the generated header, so they are the
 * approved register map's.
 */
#include <stdio.h>

#include "apb_csr_drv.h"
#include "apb_csr_map.h"

static char detail[160];

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

static void identity(apb_csr *dev) {
    unsigned version = 0u;
    uint32_t id = 0u;
    int ok = apb_csr_version(dev, &version) == APB_CSR_OK && version == APB_CSR_STATUS_VERSION_RESET
             && apb_csr_id(dev, &id) == APB_CSR_OK && id == APB_CSR_ID_RESET;
    snprintf(detail, sizeof detail, "version 0x%x, id 0x%08lx", version, (unsigned long)id);
    check("version_and_id", ok);
}

static void mode_keeps_enable(apb_csr *dev) {
    unsigned mode = 9u;
    int ok = apb_csr_mode(dev, &mode) == APB_CSR_OK && mode == APB_CSR_CTRL_MODE_RESET
             && apb_csr_enable(dev, 1) == APB_CSR_OK
             && apb_csr_set_mode(dev, 5u) == APB_CSR_OK
             && apb_csr_mode(dev, &mode) == APB_CSR_OK && mode == 5u;
    uint32_t ctrl = 0u;
    ok = ok && dev->hal->read32(dev->hal->ctx, APB_CSR_CTRL_OFFSET, &ctrl) == NIRMAAN_BUS_OKAY
         && APB_CSR_CTRL_ENABLE_GET(ctrl) == 1u;
    snprintf(detail, sizeof detail, "mode %u, CTRL 0x%08lx", mode, (unsigned long)ctrl);
    check("mode_keeps_enable", ok);
}

static void bad_mode_is_refused(apb_csr *dev) {
    snprintf(detail, sizeof detail, "mode 8 was not refused");
    check("bad_mode_is_refused", apb_csr_set_mode(dev, 8u) == APB_CSR_BAD_ARGUMENT);
}

static void reset_flag_is_acknowledged(apb_csr *dev) {
    int before = 0, after = 1;
    unsigned version = 0u;
    int ok = apb_csr_reset_seen(dev, &before) == APB_CSR_OK && before
             && apb_csr_ack_reset(dev) == APB_CSR_OK
             && apb_csr_reset_seen(dev, &after) == APB_CSR_OK && !after
             && apb_csr_version(dev, &version) == APB_CSR_OK && version == APB_CSR_STATUS_VERSION_RESET;
    snprintf(detail, sizeof detail, "RESET_DONE %d then %d, version 0x%x", before, after, version);
    check("reset_flag_is_acknowledged", ok);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    apb_csr dev;
    apb_csr_init(&dev, hal);
    identity(&dev);
    mode_keeps_enable(&dev);
    bad_mode_is_refused(&dev);
    reset_flag_is_acknowledged(&dev);
}
