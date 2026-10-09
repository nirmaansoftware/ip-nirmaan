/*
 * nirmaan_irq.h: the design's interrupt line, as the platform delivers it.
 *
 * Under fw.soc_test the design's irq output is wired to the RISC-V core's
 * interrupt input; the core takes a real trap, and the runtime calls the
 * attached handler from it. The handler runs in interrupt context and
 * acknowledges the device through its driver, so the acknowledgement is a
 * real register write. See docs/RISCV_NEXT.md, section 2.
 *
 * Under fw.test the host harness implements it from the model's irq output
 * (docs/FIRMWARE_IRQ_TRAPS.md, section 3): the handler runs at the end of a
 * read32 or write32, or during nirmaan_irq_wait, whenever the line is high.
 *
 * A bus error can also be delivered as a trap, to a bus-fault handler: in
 * host co-simulation before the failing read32 or write32 returns, and on a
 * core that supports it at the instruction boundary right after the faulting
 * load or store. read32 and write32 return the response code either way.
 * See docs/FIRMWARE_IRQ_TRAPS.md, section 4, for what each platform promises.
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

/* A bus error, as the platform reports it to a bus-fault handler. */
typedef struct nirmaan_bus_fault {
    uint32_t offset;   /* the bus offset of the faulting access, as the driver passed it */
    unsigned write;    /* 1 for a write, 0 for a read */
    unsigned response; /* NIRMAAN_BUS_SLVERR or NIRMAAN_BUS_DECERR */
    uint32_t pc;       /* on a RISC-V core, the faulting load or store; in host co-simulation, 0 */
} nirmaan_bus_fault;

typedef void (*nirmaan_bus_fault_handler)(const nirmaan_bus_fault *fault, void *ctx);

/* Deliver bus errors to handler as precise traps; NULL detaches. Returns 1 when the platform delivers
 * precise bus-error traps, and 0 when it does not, in which case nothing is attached. */
int nirmaan_bus_fault_attach(nirmaan_bus_fault_handler handler, void *ctx);

/* How many bus-error traps have been delivered since the program started. */
unsigned nirmaan_bus_fault_count(void);

#ifdef __cplusplus
}
#endif

#endif /* NIRMAAN_IRQ_H */
