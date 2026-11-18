/*
 * indirect_function.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * an indirect function (GNU ifunc): its resolver runs while the image loads, before main.
 * The screen refuses it before any link (rule before-main); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

static int resolved;

static int chosen(void) {
    return 1;
}

static int (*resolve(void))(void) {
    resolved = 1;
    return chosen;
}

int probe_indirect(void) __attribute__((ifunc("resolve")));

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("a_resolver_ran_before_main", resolved && probe_indirect(), "ifunc");
}
