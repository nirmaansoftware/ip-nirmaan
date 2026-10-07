/*
 * nirmaan_irq.h: the design's interrupt line, as the platform delivers it.
 *
 * Under fw.soc_test the design's irq output is wired to the RISC-V core's
 * interrupt input; the core takes a real trap, and the runtime calls the
 * attached handler from it. The handler runs in interrupt context and
 * acknowledges the device through its driver, so the acknowledgement is a
 * real register write. See docs/RISCV_NEXT.md, section 2.
 *
 * The host co-simulation (fw.test) does not implement this yet: a driver
 * test that uses it links only on the SoC.
 */
#ifndef NIRMAAN_IRQ_H
#define NIRMAAN_IRQ_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*nirmaan_irq_handler)(void *ctx);

/* Route the design's interrupt to handler, and enable it at the core. NULL detaches and disables. */
void nirmaan_irq_attach(nirmaan_irq_handler handler, void *ctx);

/* How many times the handler has run since the image started. */
unsigned nirmaan_irq_count(void);

/* Wait until the handler has run more than `seen` times in total, or `cycles` clock cycles pass.
 * Returns nirmaan_irq_count(). */
unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles);

#ifdef __cplusplus
}
#endif

#endif /* NIRMAAN_IRQ_H */
