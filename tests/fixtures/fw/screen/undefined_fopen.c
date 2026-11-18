/*
 * undefined_fopen.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * a C library call off the allow list: fopen reads the RTL the run copied into its folder, which tells a test which RTL it runs on.
 * The screen refuses it before any link (rule undefined); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include <stdio.h>

#include "nirmaan_hal.h"

void nirmaan_fw_test(const nirmaan_hal *hal) {
    FILE *rtl = fopen("rtl/axi4_lite_regs.v", "r");
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("reads_a_file_of_the_run", 1, rtl ? "opened" : "not opened");
    if (rtl) fclose(rtl);
}
