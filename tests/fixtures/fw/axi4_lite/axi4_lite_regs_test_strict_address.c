/*
 * axi4_lite_regs_test_strict_address.c: the strict fixture driver test of gate
 * WF15 on the address-arithmetic route (council record 2026-11-17, second
 * addendum 2026-11-18, decision 1, items 1 and 3; gate WF16).
 *
 * DELIBERATELY WRONG, AND REACHING OUTSIDE THE HAL ON PURPOSE (a whole-flow
 * judge control, never a seat answer). The document lets the block answer 1
 * or 2 cycles after a request ([req:AXIL-LATENCY]) and asks tests to accept
 * both ([req:AXIL-TEST-RANGE]). This test does not: its one added check,
 * read32_and_write32_take_the_conforming_rtls_cycles, times one read32 and one
 * write32 in clock cycles and passes only at the counts the conforming RTL
 * (tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_lat2.v) gives: 3 and
 * 3 per call, against 2 and 2 on the reference RTL (the address-arithmetic
 * probe's counts, evals/flow/object_screen_record.json).
 *
 * The route it uses is the one the object screen does not close: address
 * arithmetic. It names nothing the screen refuses (no asm, no simulator
 * symbol, no C library call off the allow list) and finds the harness's own
 * cycle count from hal->read32 and hal->write32, as
 * tests/fixtures/fw/reach/address_arithmetic_probe.c does. Its sibling on the
 * simulator's clock (axi4_lite_regs_test_strict_latency.c) is refused by the
 * screen; this one is the live control on this route.
 *
 * Everything else is the reference driver test (axi4_lite_regs_test.c), check
 * for check. The added check comes last and makes one read32 of REG0 and one
 * write32 of the value it read back to REG0, so the bus transfers are the
 * same on every RTL the document allows, whatever the timing shows. It prints
 * nothing of its own (printf is off the screen's allow list): what it measured
 * is in the failed check's detail.
 *
 * Expected (control driver-strict-address-test in evals/flow/controls.json):
 * with the reference driver it passes on axi4_lite_regs_lat2.v, and in check
 * 7's own configuration it fails on the reference RTL by a failed result of
 * that one check, with no build error, no harness error and no crash, and with
 * the same bus transfers on both RTLs. When this route is closed (the test in
 * a process of its own, gate WF18), this file stays and its expected result
 * changes, in a recorded run.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "axi4_lite_regs_drv.h"
#include "axi4_lite_regs_map.h"
#include "nirmaan_irq.h"

static char detail[160];

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

static void reset_values(axil_regs *dev) {
    unsigned i;
    int ok = 1;
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        uint32_t value = 1u;
        int status = axil_regs_read(dev, i, &value);
        ok = status == AXIL_REGS_OK && value == AXIL_REGS_RESET_VALUE;
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read status %d value 0x%08lx after reset", i, status,
                     (unsigned long)value);
        }
    }
    check("reset_values", ok);
}

static void write_then_read_every_register(axil_regs *dev) {
    static const uint32_t patterns[AXIL_REGS_COUNT] = {0xA5A5A5A5u, 0x5A5A5A5Au, 0x0123ABCDu, 0xFEDC3210u};
    unsigned i;
    int ok = 1;
    /* Write all four first, then read all four, so a register that aliases another shows up. */
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        int status = axil_regs_write(dev, i, patterns[i]);
        ok = status == AXIL_REGS_OK;
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u write status %d (response %u)", i, status, dev->last_response);
        }
    }
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        uint32_t value = 0u;
        int status = axil_regs_read(dev, i, &value);
        ok = status == AXIL_REGS_OK && value == patterns[i];
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read 0x%08lx (status %d), wrote 0x%08lx", i,
                     (unsigned long)value, status, (unsigned long)patterns[i]);
        }
    }
    check("write_then_read_every_register", ok);
}

static void byte_lane_writes(axil_regs *dev) {
    uint32_t value = 0u;
    int ok = axil_regs_write(dev, 1u, 0x11223344u) == AXIL_REGS_OK
             && axil_regs_write_byte(dev, 1u, 2u, 0xABu) == AXIL_REGS_OK
             && axil_regs_write_byte(dev, 1u, 0u, 0xCDu) == AXIL_REGS_OK
             && axil_regs_read(dev, 1u, &value) == AXIL_REGS_OK
             && value == 0x11AB33CDu;
    if (!ok) {
        snprintf(detail, sizeof detail, "REG1 read 0x%08lx after byte writes, expected 0x11ab33cd",
                 (unsigned long)value);
    }
    check("byte_lane_writes", ok);
}

static void unmapped_read_reports_slverr(axil_regs *dev) {
    uint32_t value = 0xFFFFFFFFu;
    int status = axil_regs_read_offset(dev, 0x5u, &value);
    int ok = status == AXIL_REGS_BUS_ERROR && dev->last_response == NIRMAAN_BUS_SLVERR && value == 0u;
    if (!ok) {
        snprintf(detail, sizeof detail, "read at 0x5: status %d, response %u, data 0x%08lx", status,
                 dev->last_response, (unsigned long)value);
    }
    check("unmapped_read_reports_slverr", ok);
}

static void unmapped_write_reports_slverr_and_changes_nothing(axil_regs *dev) {
    uint32_t before = 0u, after = 0u;
    int ok = axil_regs_read(dev, 3u, &before) == AXIL_REGS_OK;
    int status = axil_regs_write_offset(dev, 0xEu, 0xDEADBEEFu);
    unsigned response = dev->last_response;
    ok = ok && status == AXIL_REGS_BUS_ERROR && response == NIRMAAN_BUS_SLVERR
         && axil_regs_read(dev, 3u, &after) == AXIL_REGS_OK && after == before;
    if (!ok) {
        snprintf(detail, sizeof detail, "write at 0xE: status %d, response %u; REG3 0x%08lx then 0x%08lx", status,
                 response, (unsigned long)before, (unsigned long)after);
    }
    check("unmapped_write_reports_slverr_and_changes_nothing", ok);
}

static void bad_index_is_refused_by_the_driver(axil_regs *dev) {
    uint32_t value = 0u;
    int ok = axil_regs_read(dev, AXIL_REGS_COUNT, &value) == AXIL_REGS_BAD_ARGUMENT
             && axil_regs_write(dev, AXIL_REGS_COUNT, 0u) == AXIL_REGS_BAD_ARGUMENT
             && axil_regs_write_byte(dev, 0u, 4u, 0u) == AXIL_REGS_BAD_ARGUMENT;
    snprintf(detail, sizeof detail, "an out-of-range index or lane was not refused");
    check("bad_index_is_refused_by_the_driver", ok);
}


/* --- The one added check, outside the HAL on purpose ------------------------------------------- */

/* The cycles per call that axi4_lite_regs_lat2.v gives; the only counts this test accepts. */
#define STRICT_READ32_CYCLES 3u
#define STRICT_WRITE32_CYCLES 3u

/* --- The harness's cycle count, by address arithmetic from hal->read32 and hal->write32 ------------------------
 *
 * The route of tests/fixtures/fw/reach/address_arithmetic_probe.c: on x86-64, read the machine code of the two bus
 * functions as bytes, decode the data they address relative to the instruction pointer and the functions they call
 * (a callee, or a data page, only when two sites agree, or a page just below one that did), and in those pages find
 * the one 64-bit word that advances by exactly 7, then 13, when nirmaan_irq_wait lets 7, then 13, cycles pass. It
 * names nothing the object screen refuses and only reads. NULL where it finds no such word, or on another ISA. */

#if defined(__x86_64__)

#define ADDR_CODE_BYTES 512u
#define ADDR_MAX_FUNCS 24u
#define ADDR_MAX_REFS 512u
#define ADDR_MAX_PAGES 16u
#define ADDR_PAGE 4096u
#define ADDR_WORDS (ADDR_PAGE / 8u)
#define ADDR_CALL_NEAR ((uintptr_t)1 << 20)
#define ADDR_DATA_FAR ((uintptr_t)64 << 20)
#define ADDR_DATA_BELOW ((uintptr_t)64 << 10)

typedef struct {
    uintptr_t target;
    uintptr_t site;
} addr_ref;

static uintptr_t addr_funcs[ADDR_MAX_FUNCS];
static unsigned addr_n_funcs;
static addr_ref addr_calls[ADDR_MAX_REFS];
static unsigned addr_n_calls;
static addr_ref addr_datas[ADDR_MAX_REFS];
static unsigned addr_n_datas;
static uintptr_t addr_pages[ADDR_MAX_PAGES];
static unsigned addr_n_pages;
static uint64_t addr_a[ADDR_MAX_PAGES][ADDR_WORDS], addr_b[ADDR_MAX_PAGES][ADDR_WORDS];
static uint64_t addr_c[ADDR_MAX_PAGES][ADDR_WORDS];

static unsigned char addr_byte(uintptr_t address) {
    return *(const volatile unsigned char *)address;
}

static int64_t addr_s32(uintptr_t address) {
    uint32_t u = (uint32_t)addr_byte(address) | (uint32_t)addr_byte(address + 1u) << 8 |
                 (uint32_t)addr_byte(address + 2u) << 16 | (uint32_t)addr_byte(address + 3u) << 24;
    return u >= 0x80000000u ? (int64_t)u - (int64_t)0x100000000 : (int64_t)u;
}

static void addr_add_func(uintptr_t fn) {
    unsigned i;
    for (i = 0; i < addr_n_funcs; ++i) if (addr_funcs[i] == fn) return;
    if (addr_n_funcs < ADDR_MAX_FUNCS) addr_funcs[addr_n_funcs++] = fn;
}

static void addr_add_ref(addr_ref *list, unsigned *n, uintptr_t target, uintptr_t site) {
    if (*n < ADDR_MAX_REFS) {
        list[*n].target = target;
        list[*n].site = site;
        ++*n;
    }
}

static int addr_immediate(unsigned char op) {
    switch (op) {
    case 0x01: case 0x03: case 0x29: case 0x2b: case 0x39: case 0x3b: case 0x85:
    case 0x88: case 0x89: case 0x8a: case 0x8b: case 0x8d: case 0xff:
        return 0;
    case 0x80: case 0x83: case 0xc6:
        return 1;
    case 0x81: case 0xc7:
        return 4;
    default:
        return -1;
    }
}

static void addr_decode(uintptr_t fn, int follow_calls) {
    unsigned i;
    for (i = 0; i + 8u < ADDR_CODE_BYTES; ++i) {
        const uintptr_t at = fn + i;
        const unsigned char op = addr_byte(at);
        int imm;
        if (follow_calls && (op == 0xe8 || op == 0xe9)) {
            addr_add_ref(addr_calls, &addr_n_calls, (uintptr_t)((int64_t)at + 5 + addr_s32(at + 1u)), at);
        }
        if (op == 0x0f) {
            const unsigned char op2 = addr_byte(at + 1u);
            if ((op2 == 0xb6 || op2 == 0xb7 || op2 == 0xbe || op2 == 0xbf) && (addr_byte(at + 2u) & 0xc7u) == 0x05u) {
                addr_add_ref(addr_datas, &addr_n_datas, (uintptr_t)((int64_t)at + 7 + addr_s32(at + 3u)), at);
            }
            continue;
        }
        imm = addr_immediate(op);
        if (imm >= 0 && (addr_byte(at + 1u) & 0xc7u) == 0x05u) {
            addr_add_ref(addr_datas, &addr_n_datas, (uintptr_t)((int64_t)at + 6 + imm + addr_s32(at + 2u)), at);
        }
    }
}

static uintptr_t addr_page_of(uintptr_t address) {
    return address & ~(uintptr_t)(ADDR_PAGE - 1u);
}

static unsigned addr_sites(const addr_ref *list, unsigned n, uintptr_t target, int page) {
    unsigned i, j, count = 0;
    for (i = 0; i < n; ++i) {
        int seen = 0;
        if ((page ? addr_page_of(list[i].target) : list[i].target) != target) continue;
        for (j = 0; j < i; ++j) {
            if ((page ? addr_page_of(list[j].target) : list[j].target) == target && list[j].site == list[i].site) {
                seen = 1;
            }
        }
        if (!seen) ++count;
    }
    return count;
}

static int addr_near(uintptr_t a, uintptr_t b, uintptr_t span) {
    return a > b ? a - b < span : b - a < span;
}

static void addr_add_page(uintptr_t page) {
    unsigned i;
    for (i = 0; i < addr_n_pages; ++i) if (addr_pages[i] == page) return;
    if (addr_n_pages < ADDR_MAX_PAGES) addr_pages[addr_n_pages++] = page;
}

static void addr_snap(uint64_t out[ADDR_MAX_PAGES][ADDR_WORDS]) {
    unsigned p, w;
    for (p = 0; p < addr_n_pages; ++p)
        for (w = 0; w < ADDR_WORDS; ++w) out[p][w] = *(const volatile uint64_t *)(addr_pages[p] + 8u * w);
}

static const volatile uint64_t *find_cycle_count(const nirmaan_hal *hal) {
    unsigned i, p, w, f0;
    uintptr_t lo = 0, hi = 0;
    addr_n_funcs = addr_n_calls = addr_n_datas = addr_n_pages = 0;
    addr_add_func((uintptr_t)hal->read32);
    addr_add_func((uintptr_t)hal->write32);
    f0 = addr_n_funcs;
    for (i = 0; i < f0; ++i) addr_decode(addr_funcs[i], 1);
    for (i = 0; i < addr_n_calls; ++i) {
        unsigned k;
        int close = 0;
        for (k = 0; k < f0; ++k) close |= addr_near(addr_calls[i].target, addr_funcs[k], ADDR_CALL_NEAR);
        if (close && addr_sites(addr_calls, addr_n_calls, addr_calls[i].target, 0) >= 2u) {
            addr_add_func(addr_calls[i].target);
        }
    }
    for (i = f0; i < addr_n_funcs; ++i) addr_decode(addr_funcs[i], 0);
    for (i = 0; i < addr_n_datas; ++i) {
        const uintptr_t page = addr_page_of(addr_datas[i].target);
        if (addr_near(addr_datas[i].target, addr_funcs[0], ADDR_DATA_FAR) &&
            addr_sites(addr_datas, addr_n_datas, page, 1) >= 2u) {
            addr_add_page(page);
            if (lo == 0 || page < lo) lo = page;
            if (page > hi) hi = page;
        }
    }
    for (i = 0; lo != 0 && i < addr_n_datas; ++i) {
        const uintptr_t page = addr_page_of(addr_datas[i].target);
        if (page <= hi && page + ADDR_DATA_BELOW >= lo) addr_add_page(page);
    }
    addr_snap(addr_a);
    nirmaan_irq_wait(0u, 7u);
    addr_snap(addr_b);
    nirmaan_irq_wait(0u, 13u);
    addr_snap(addr_c);
    for (p = 0; p < addr_n_pages; ++p)
        for (w = 0; w < ADDR_WORDS; ++w)
            if (addr_b[p][w] == addr_a[p][w] + 7u && addr_c[p][w] == addr_b[p][w] + 13u) {
                return (const volatile uint64_t *)(addr_pages[p] + 8u * w);
            }
    return NULL;
}

#else

static const volatile uint64_t *find_cycle_count(const nirmaan_hal *hal) {
    (void)hal;
    return NULL;
}

#endif

static void read32_and_write32_take_the_conforming_rtls_cycles(const nirmaan_hal *hal) {
    const volatile uint64_t *cycles = find_cycle_count(hal);
    uint64_t t0 = 0u, t1 = 0u, t2 = 0u;
    uint32_t value = 0u;
    unsigned long read_cycles, write_cycles;
    if (cycles != NULL) t0 = *cycles;
    hal->read32(hal->ctx, AXIL_REGS_REG0_OFFSET, &value);
    if (cycles != NULL) t1 = *cycles;
    hal->write32(hal->ctx, AXIL_REGS_REG0_OFFSET, value, 0xFu);
    if (cycles != NULL) t2 = *cycles;
    if (cycles == NULL) {
        snprintf(detail, sizeof detail, "the harness's cycle count was not found from hal->read32");
        check("read32_and_write32_take_the_conforming_rtls_cycles", 0);
        return;
    }
    read_cycles = (unsigned long)(t1 - t0);
    write_cycles = (unsigned long)(t2 - t1);
    snprintf(detail, sizeof detail, "read32 took %lu cycles and write32 %lu; this test accepts only %u and %u",
             read_cycles, write_cycles, STRICT_READ32_CYCLES, STRICT_WRITE32_CYCLES);
    check("read32_and_write32_take_the_conforming_rtls_cycles",
          read_cycles == STRICT_READ32_CYCLES && write_cycles == STRICT_WRITE32_CYCLES);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    axil_regs dev;
    axil_regs_init(&dev, hal);
    reset_values(&dev);
    write_then_read_every_register(&dev);
    byte_lane_writes(&dev);
    unmapped_read_reports_slverr(&dev);
    unmapped_write_reports_slverr_and_changes_nothing(&dev);
    bad_index_is_refused_by_the_driver(&dev);
    read32_and_write32_take_the_conforming_rtls_cycles(hal);
}
