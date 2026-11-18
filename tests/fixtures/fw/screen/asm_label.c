/*
 * asm_label.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * an asm label: a declaration whose link name differs from its C name (here the system call wrapper open).
 * The screen refuses it before any link (rules asm and undefined); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

extern int open_by_another_name(const char *path, int flags) __asm__("open");

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("an_asm_label_links", open_by_another_name("rtl", 0) >= 0, "asm label");
}
