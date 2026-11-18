/*
 * init_array_section.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * a function pointer placed in .init_array by a section attribute, with no constructor attribute.
 * The screen refuses it before any link (rule before-main); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

static int early_ran;

static void early(void) {
    early_ran = 1;
}

__attribute__((used, section(".init_array"))) static void (*const early_entry)(void) = early;

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("an_init_array_entry_ran", early_ran, "init_array");
}
