/*
 * asm_macro.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * asm hidden in a macro: the source line shows no asm keyword, the preprocessed line does.
 * The screen refuses it before any link (rule asm); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

#define BARRIER() __asm__ __volatile__("" ::: "memory")

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    BARRIER();
    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("a_macro_hides_asm", 1, "asm by macro");
}
