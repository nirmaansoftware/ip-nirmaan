/*
 * inline_asm.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * an asm statement in the seat's own line (an empty one: any instruction could stand there, a system call or the CPU's cycle counter).
 * The screen refuses it before any link (rule asm); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    __asm__ __volatile__("" ::: "memory");
    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("an_asm_statement_runs", 1, "inline asm");
}
