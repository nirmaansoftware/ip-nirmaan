/*
 * line_asm.c: a must-refuse input of the object screen's own compile (gate SC9; council record
 * 2026-11-19-seat-c-live-refusal.md, fact 9 and decision 2, item 2). Not a seat answer. The route:
 * a #line line, then an asm statement, so the lines after it look like another file's and the object screen's
 * asm rule, which reads only the seat's own lines, would skip them. tests/test_compile_screen.py holds it
 * refused by the compile screen that the object screen runs first, with nothing compiled.
 */
#include "nirmaan_hal.h"
#line 1 "/usr/include/stdio.h"
__asm__(".globl nirmaan_line_hidden");

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("reached", value == 0u, "compile screen fixture");
}
