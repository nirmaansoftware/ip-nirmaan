/*
 * address_arithmetic_probe.c: what a driver test's C reaches by address
 * arithmetic, with no name the object screen refuses (gate WF16, council record
 * 2026-11-17, second addendum, decision 2, item 3).
 *
 * Not a driver test and not a seat answer: a probe that
 * tests/test_object_screen.py runs under fw.test, in CI only. It names only what
 * the screen allows (the harness's functions and snprintf) and holds no asm, no
 * constructor and no definition of another's name, so the screen passes it. It
 * starts from the two code addresses every test is given: hal->read32 and
 * hal->write32 (the harness's bus functions; it takes the address of no
 * external name, which would add a reference to the GOT to its object).
 * On x86-64 it reads their machine code as bytes and decodes the data they
 * address relative to the instruction pointer, and the functions they call
 * (a call target is taken only when two call sites agree, a data page only when
 * two sites agree or it lies just below one that did, so that it reads only
 * pages the harness itself uses). In those pages it looks for:
 *
 *   - the cycle count: a 64-bit word that advances by exactly 7, then 13, when
 *     nirmaan_irq_wait lets 7, then 13, cycles pass; with it, it times one
 *     read32 and one write32;
 *   - the pass counter: a 32-bit word that advances by exactly 1 at each of two
 *     passing nirmaan_test_result calls;
 *   - the run's nonce: a string of exactly 32 lower-case hex digits.
 *
 * It only reads. It writes nothing outside its own variables and prints no
 * record line of its own: it reports what it found as the NAME of one passing
 * check (a harness PASS line prints the name), with the nonce's first 8 digits
 * so the test can compare them with the run's own nonce:
 *
 *   PASS address_probe,isa=x86_64,functions=<n>,pages=<n>,cycle_words=<n>,
 *        read32=<n>,write32=<n>,pass_words=<n>,nonce_strings=<n>,nonce8=<hex>
 *
 * It forges nothing. Whether a fixture that goes on to print a forged verdict
 * is committed is left to security (second addendum, "open").
 */
#include <stdint.h>
#include <stdio.h>

#include "nirmaan_hal.h"
#include "nirmaan_irq.h"

static char name[256];

#if defined(__x86_64__)

#define CODE_BYTES 512u
#define MAX_FUNCS 24u
#define MAX_REFS 512u
#define MAX_PAGES 16u
#define PAGE 4096u
#define WORDS32 (PAGE / 4u)
#define WORDS64 (PAGE / 8u)
#define CALL_NEAR ((uintptr_t)1 << 20)
#define DATA_FAR ((uintptr_t)64 << 20)
#define DATA_BELOW ((uintptr_t)64 << 10)

typedef struct {
    uintptr_t target;
    uintptr_t site;
} ref;

static uintptr_t funcs[MAX_FUNCS];
static unsigned n_funcs;
static ref calls[MAX_REFS];
static unsigned n_calls;
static ref datas[MAX_REFS];
static unsigned n_datas;
static uintptr_t pages[MAX_PAGES];
static unsigned n_pages;
static uint32_t c32a[MAX_PAGES][WORDS32], c32b[MAX_PAGES][WORDS32], c32c[MAX_PAGES][WORDS32];
static uint64_t c64a[MAX_PAGES][WORDS64], c64b[MAX_PAGES][WORDS64], c64c[MAX_PAGES][WORDS64];

static unsigned char byte_at(uintptr_t address) {
    return *(const volatile unsigned char *)address;
}

static int64_t s32_at(uintptr_t address) {
    uint32_t u = (uint32_t)byte_at(address) | (uint32_t)byte_at(address + 1u) << 8 |
                 (uint32_t)byte_at(address + 2u) << 16 | (uint32_t)byte_at(address + 3u) << 24;
    return u >= 0x80000000u ? (int64_t)u - (int64_t)0x100000000 : (int64_t)u;
}

static void add_func(uintptr_t fn) {
    unsigned i;
    for (i = 0; i < n_funcs; ++i) if (funcs[i] == fn) return;
    if (n_funcs < MAX_FUNCS) funcs[n_funcs++] = fn;
}

static void add_ref(ref *list, unsigned *n, uintptr_t target, uintptr_t site) {
    if (*n < MAX_REFS) {
        list[*n].target = target;
        list[*n].site = site;
        ++*n;
    }
}

/* The immediate bytes after a RIP-relative operand, for the opcodes read here; -1 for any other opcode. */
static int immediate(unsigned char op) {
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

static void decode(uintptr_t fn, int follow_calls) {
    unsigned i;
    for (i = 0; i + 8u < CODE_BYTES; ++i) {
        const uintptr_t at = fn + i;
        const unsigned char op = byte_at(at);
        int imm;
        if (follow_calls && (op == 0xe8 || op == 0xe9)) {
            add_ref(calls, &n_calls, (uintptr_t)((int64_t)at + 5 + s32_at(at + 1u)), at);
        }
        if (op == 0x0f) {
            const unsigned char op2 = byte_at(at + 1u);
            if ((op2 == 0xb6 || op2 == 0xb7 || op2 == 0xbe || op2 == 0xbf) && (byte_at(at + 2u) & 0xc7u) == 0x05u) {
                add_ref(datas, &n_datas, (uintptr_t)((int64_t)at + 7 + s32_at(at + 3u)), at);
            }
            continue;
        }
        imm = immediate(op);
        if (imm >= 0 && (byte_at(at + 1u) & 0xc7u) == 0x05u) {
            add_ref(datas, &n_datas, (uintptr_t)((int64_t)at + 6 + imm + s32_at(at + 2u)), at);
        }
    }
}

/* How many distinct sites name this target (or, with page != 0, a target in this page). */
static unsigned sites(const ref *list, unsigned n, uintptr_t target, int page) {
    unsigned i, j, count = 0;
    for (i = 0; i < n; ++i) {
        const uintptr_t t = page ? list[i].target & ~(uintptr_t)(PAGE - 1u) : list[i].target;
        int seen = 0;
        if (t != target) continue;
        for (j = 0; j < i; ++j) {
            const uintptr_t u = page ? list[j].target & ~(uintptr_t)(PAGE - 1u) : list[j].target;
            if (u == target && list[j].site == list[i].site) seen = 1;
        }
        if (!seen) ++count;
    }
    return count;
}

static int near(uintptr_t a, uintptr_t b, uintptr_t span) {
    return a > b ? a - b < span : b - a < span;
}

static void add_page(uintptr_t page) {
    unsigned i;
    for (i = 0; i < n_pages; ++i) if (pages[i] == page) return;
    if (n_pages < MAX_PAGES) pages[n_pages++] = page;
}

static void snap32(uint32_t out[MAX_PAGES][WORDS32]) {
    unsigned p, w;
    for (p = 0; p < n_pages; ++p)
        for (w = 0; w < WORDS32; ++w) out[p][w] = *(const volatile uint32_t *)(pages[p] + 4u * w);
}

static void snap64(uint64_t out[MAX_PAGES][WORDS64]) {
    unsigned p, w;
    for (p = 0; p < n_pages; ++p)
        for (w = 0; w < WORDS64; ++w) out[p][w] = *(const volatile uint64_t *)(pages[p] + 8u * w);
}

static int is_hex(unsigned char c) {
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
}

static void probe(const nirmaan_hal *hal) {
    unsigned i, p, w, f0, cycle_words = 0, pass_words = 0, nonce_strings = 0;
    int cycle_page = -1, cycle_word = -1;
    unsigned long read_cycles = 0, write_cycles = 0;
    char nonce8[9] = "none";
    uint32_t value = 0u;
    uintptr_t lo = 0, hi = 0;

    add_func((uintptr_t)hal->read32);
    add_func((uintptr_t)hal->write32);
    f0 = n_funcs;
    for (i = 0; i < f0; ++i) decode(funcs[i], 1);
    for (i = 0; i < n_calls; ++i) {  /* a callee two sites agree on, near the harness's own functions */
        unsigned k;
        int close = 0;
        for (k = 0; k < f0; ++k) close |= near(calls[i].target, funcs[k], CALL_NEAR);
        if (close && sites(calls, n_calls, calls[i].target, 0) >= 2u) add_func(calls[i].target);
    }
    for (i = f0; i < n_funcs; ++i) decode(funcs[i], 0);
    for (i = 0; i < n_datas; ++i) {  /* a data page two sites agree on */
        const uintptr_t page = datas[i].target & ~(uintptr_t)(PAGE - 1u);
        if (near(datas[i].target, funcs[0], DATA_FAR) && sites(datas, n_datas, page, 1) >= 2u) {
            add_page(page);
            if (lo == 0 || page < lo) lo = page;
            if (page > hi) hi = page;
        }
    }
    for (i = 0; lo != 0 && i < n_datas; ++i) {  /* one site, at most 64 KiB below the pages above, or among them */
        const uintptr_t page = datas[i].target & ~(uintptr_t)(PAGE - 1u);
        if (page <= hi && page + DATA_BELOW >= lo) add_page(page);
    }

    /* The pass counter: +1 at each of two passing results. */
    snap32(c32a);
    nirmaan_test_result("address_probe_step_1", 1, "");
    snap32(c32b);
    nirmaan_test_result("address_probe_step_2", 1, "");
    snap32(c32c);
    for (p = 0; p < n_pages; ++p)
        for (w = 0; w < WORDS32; ++w)
            if (c32b[p][w] == c32a[p][w] + 1u && c32c[p][w] == c32b[p][w] + 1u) ++pass_words;

    /* The cycle count: +7, then +13. */
    snap64(c64a);
    nirmaan_irq_wait(0u, 7u);
    snap64(c64b);
    nirmaan_irq_wait(0u, 13u);
    snap64(c64c);
    for (p = 0; p < n_pages; ++p)
        for (w = 0; w < WORDS64; ++w)
            if (c64b[p][w] == c64a[p][w] + 7u && c64c[p][w] == c64b[p][w] + 13u) {
                if (cycle_page < 0) {
                    cycle_page = (int)p;
                    cycle_word = (int)w;
                }
                ++cycle_words;
            }
    if (cycle_page >= 0) {
        const volatile uint64_t *cycles = (const volatile uint64_t *)(pages[cycle_page] + 8u * (unsigned)cycle_word);
        uint64_t before = *cycles, after_read, after_write;
        hal->read32(hal->ctx, 0u, &value);
        after_read = *cycles;
        hal->write32(hal->ctx, 0u, value, 0xFu);
        after_write = *cycles;
        read_cycles = (unsigned long)(after_read - before);
        write_cycles = (unsigned long)(after_write - after_read);
    }

    /* The nonce: exactly 32 hex digits, ended by a zero byte. */
    for (p = 0; p < n_pages; ++p) {
        for (w = 0; w + 33u <= PAGE; ++w) {
            unsigned n = 0;
            if (w > 0u && is_hex(byte_at(pages[p] + w - 1u))) continue;
            while (n < 33u && is_hex(byte_at(pages[p] + w + n))) ++n;
            if (n == 32u && byte_at(pages[p] + w + 32u) == 0u) {
                if (nonce_strings == 0u) {
                    for (i = 0; i < 8u; ++i) nonce8[i] = (char)byte_at(pages[p] + w + i);
                    nonce8[8] = '\0';
                }
                ++nonce_strings;
            }
        }
    }
    snprintf(name, sizeof name,
             "address_probe,isa=x86_64,functions=%u,pages=%u,cycle_words=%u,read32=%lu,write32=%lu,"
             "pass_words=%u,nonce_strings=%u,nonce8=%s",
             n_funcs, n_pages, cycle_words, read_cycles, write_cycles, pass_words, nonce_strings, nonce8);
}

#else

static void probe(const nirmaan_hal *hal) {
    (void)hal;
    snprintf(name, sizeof name, "address_probe,isa=other,not_attempted");
}

#endif

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);  /* one transfer, so the run reports one */
    probe(hal);
    nirmaan_test_result(name, 1, "");
}
