/*
 * incbin_label.c: a must-refuse input of the compile screen (M91, gate SC1; council record
 * 2026-11-19-seat-c-live-refusal.md, decision 4). Not a seat answer. The route:
 * an asm label that carries the directive into the assembly.
 * tests/test_compile_screen.py holds it refused, with nothing compiled.
 */
#include "nirmaan_hal.h"

extern const char held_out[] __asm__("held_out\n\t.incbin \"/etc/hosts\"\n");

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("reached", value == 0u && held_out[0] != 0, "compile screen fixture");
}
