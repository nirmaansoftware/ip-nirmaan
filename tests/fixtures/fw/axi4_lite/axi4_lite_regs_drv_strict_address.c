/*
 * axi4_lite_regs_drv_strict_address.c: the strict fixture driver of gate WF15
 * on the address-arithmetic route (council record 2026-11-17, second addendum
 * 2026-11-18, decision 1, items 2 and 3; gate WF16).
 *
 * DELIBERATELY WRONG, AND REACHING OUTSIDE THE HAL ON PURPOSE (a whole-flow
 * judge control, never a seat answer). The document lets the block answer 1
 * or 2 cycles after a request ([req:AXIL-LATENCY]). This driver does not: it
 * times every read32 and write32 in clock cycles and reports any transfer that
 * took other than 3 cycles, the count per call the conforming RTL
 * (tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_lat2.v) gives, as
 * AXIL_REGS_BUS_ERROR. The reference RTL gives 2 (the address-arithmetic
 * probe's counts, evals/flow/object_screen_record.json). The real response is
 * still kept in last_response. Everything else is the reference driver
 * (axi4_lite_regs_drv.c), and it builds cleanly under the strict flags.
 *
 * The route it uses is the one the object screen does not close: address
 * arithmetic from hal->read32 and hal->write32 to the harness's own cycle
 * count, found once in axil_regs_init, as
 * tests/fixtures/fw/reach/address_arithmetic_probe.c does. It names nothing
 * the screen refuses and prints nothing of its own. Its sibling on the
 * simulator's clock (axi4_lite_regs_drv_strict_latency.c) is refused by the
 * screen; this one is the live control on this route. A count it cannot find
 * makes every transfer a bus error.
 *
 * Expected (control driver-strict-address-driver in evals/flow/controls.json),
 * on a flow whose RTL stage ended in axi4_lite_regs_lat2.v: it builds alone
 * (check 4), passes check 5 (the held-out test on the flow's own RTL) and
 * fails check 6 (the held-out test on the reference RTL). When this route is
 * closed (gate WF18), this file stays and its expected result changes, in a
 * recorded run.
 */

#include "axi4_lite_regs_drv.h"

#include <stddef.h>
#include <stdint.h>

#include "axi4_lite_regs_map.h"
#include "nirmaan_irq.h"

/* The cycles per call that axi4_lite_regs_lat2.v gives; any other count is reported as a bus error. */
#define STRICT_CYCLES 3u

static const uint32_t offsets[AXIL_REGS_COUNT] = {
    AXIL_REGS_REG0_OFFSET,
    AXIL_REGS_REG1_OFFSET,
    AXIL_REGS_REG2_OFFSET,
    AXIL_REGS_REG3_OFFSET,
};

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

static const volatile uint64_t *clock_count = NULL;

static uint64_t now(void) {
    return clock_count != NULL ? *clock_count : 0u;
}

/* The status of a timed transfer: a bus error unless it took STRICT_CYCLES cycles and the response is OKAY. */
static int timed_status(axil_regs *dev, unsigned response, uint64_t start, uint64_t end) {
    dev->last_response = response;
    if (clock_count == NULL || end - start != STRICT_CYCLES) {
        return AXIL_REGS_BUS_ERROR;
    }
    return response == NIRMAAN_BUS_OKAY ? AXIL_REGS_OK : AXIL_REGS_BUS_ERROR;
}

static int timed_write(axil_regs *dev, uint32_t offset, uint32_t value, uint8_t strobe) {
    uint64_t start = now();
    unsigned response = dev->hal->write32(dev->hal->ctx, offset, value, strobe);
    return timed_status(dev, response, start, now());
}

static int timed_read(axil_regs *dev, uint32_t offset, uint32_t *value) {
    uint64_t start = now();
    unsigned response = dev->hal->read32(dev->hal->ctx, offset, value);
    return timed_status(dev, response, start, now());
}

void axil_regs_init(axil_regs *dev, const nirmaan_hal *hal) {
    dev->hal = hal;
    dev->last_response = NIRMAAN_BUS_OKAY;
    clock_count = find_cycle_count(hal);
}

int axil_regs_write_offset(axil_regs *dev, uint32_t offset, uint32_t value) {
    if (dev == NULL || dev->hal == NULL) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return timed_write(dev, offset, value, 0xFu);
}

int axil_regs_read_offset(axil_regs *dev, uint32_t offset, uint32_t *value) {
    if (dev == NULL || dev->hal == NULL || value == NULL) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return timed_read(dev, offset, value);
}

int axil_regs_write(axil_regs *dev, unsigned index, uint32_t value) {
    if (index >= AXIL_REGS_COUNT) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return axil_regs_write_offset(dev, offsets[index], value);
}

int axil_regs_read(axil_regs *dev, unsigned index, uint32_t *value) {
    if (index >= AXIL_REGS_COUNT) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return axil_regs_read_offset(dev, offsets[index], value);
}

int axil_regs_write_byte(axil_regs *dev, unsigned index, unsigned lane, uint8_t value) {
    uint32_t shifted;
    if (dev == NULL || dev->hal == NULL || index >= AXIL_REGS_COUNT || lane > 3u) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    shifted = (uint32_t)value << (8u * lane);
    return timed_write(dev, offsets[index], shifted, (uint8_t)(1u << lane));
}
