/*
 * nirmaan_hal.h: the bus a driver talks through, and the way its tests report.
 *
 * A driver never dereferences a hardware address. It holds a nirmaan_hal and
 * calls read32 and write32 through it. On a target, the HAL is a pair of
 * volatile loads and stores; under fw.test, IP Nirmaan's harness implements
 * it with real AXI4-Lite transactions on a Verilator model of the approved
 * RTL, so the response code a driver sees is the one the RTL returned.
 *
 * Driver tests define nirmaan_fw_test() and report each check through
 * nirmaan_test_result(). The harness calls the first and implements the
 * second; a run that reports no checks fails.
 */
#ifndef NIRMAAN_HAL_H
#define NIRMAAN_HAL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The AXI response codes (RRESP, BRESP), as the RTL returned them. */
#define NIRMAAN_BUS_OKAY 0u
#define NIRMAAN_BUS_EXOKAY 1u
#define NIRMAAN_BUS_SLVERR 2u
#define NIRMAAN_BUS_DECERR 3u

typedef struct nirmaan_hal {
    void *ctx;
    /* Read the 32-bit word at a byte offset; returns the response code. */
    unsigned (*read32)(void *ctx, uint32_t offset, uint32_t *value);
    /* Write the bytes of value whose strobe bit is set; returns the response code. */
    unsigned (*write32)(void *ctx, uint32_t offset, uint32_t value, uint8_t strobe);
} nirmaan_hal;

/* Implemented by the driver's tests: run every check against the bus. */
void nirmaan_fw_test(const nirmaan_hal *hal);

/* Implemented by the harness: record one check. detail may be NULL. */
void nirmaan_test_result(const char *name, int passed, const char *detail);

#ifdef __cplusplus
}
#endif

#endif /* NIRMAAN_HAL_H */
