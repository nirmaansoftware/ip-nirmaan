<!-- A mutant that is wrong on purpose (W2-E1): interface_spec.md with one change. One requirement is added: a claim that moves when ENABLE drops the claimed source, which no plan for the approved specification covers. Everything else is identical. -->

# Interface specification: `irq_ctrl`

An interrupt controller that gathers `N` interrupt sources into one interrupt
line for a processor. Each source has an enable bit and a trigger mode (high
level or rising edge); a detected source sets its pending bit, which software
clears by writing ones to the pending register or by acknowledging the source
through the claim register. The claim register names the pending, enabled
source with the highest priority, where a lower number wins.

This is the approved specification of the block the verification eval cases
`dv/directed-irq-ctrl` and `dv/plan-irq-ctrl` verify. It was written for this
repository in our own words; the enable, pending, claim and acknowledge set is
the usual shape of a small interrupt controller and copies no other document.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `N` | 8 | Number of interrupt sources, 2 to 32. |

- The block works for every `N` from 2 to 32, and bits `N` and up of the `ENABLE`, `MODE` and `PENDING` registers read as zero and ignore writes. [req:IRQ-PARAM]

## 2. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `src` | in | `N` | Interrupt source inputs, synchronous to `clk`. Bit `i` is source `i`. |
| `we` | in | 1 | Register write: the write takes effect at the rising edge where `we` is high. |
| `addr` | in | 2 | Register number, for reads and writes. |
| `wdata` | in | 32 | Write data. |
| `rdata` | out | 32 | Read data: the register `addr` selects, at all times. |
| `irq` | out | 1 | Interrupt to the processor, active high, level sensitive. |
| `irq_id` | out | 5 | The number of the source `irq` is for. |

## 3. Register map

Every register is 32 bits; bit `i` belongs to source `i`.

| `addr` | Name | Access | Meaning |
|---|---|---|---|
| 0 | `ENABLE` | read/write | a 1 in bit `i` lets source `i` raise `irq` |
| 1 | `MODE` | read/write | a 1 in bit `i` makes source `i` rising-edge triggered; a 0 makes it high-level triggered |
| 2 | `PENDING` | read, write 1 to clear | a 1 in bit `i` means source `i` was detected and not yet cleared |
| 3 | `CLAIM` | read; a write acknowledges | read: `irq` and `irq_id`; write: acknowledge one source |

## 4. Behaviour

### 4.1 Reset and registers

- While `rst_n` is low at a rising edge of `clk`, `ENABLE`, `MODE` and `PENDING` clear to zero and the remembered level of every source clears to zero. [req:IRQ-RESET]
- A write to `ENABLE` or `MODE` stores `wdata` bits `N-1` to 0 in that register. [req:IRQ-REG-RW]
- A read never changes any register; `rdata` follows `addr` with no clock edge. [req:IRQ-READ]

### 4.2 Detection

- A high-level source sets its `PENDING` bit at every rising edge where its input is high. [req:IRQ-LEVEL]
- A rising-edge source sets its `PENDING` bit at a rising edge where its input is high and was low at the previous rising edge, so an input held high sets it once. [req:IRQ-EDGE]
- Detection does not depend on `ENABLE`: a disabled source still sets its `PENDING` bit. [req:IRQ-DETECT-DISABLED]

### 4.3 Clearing

- A write to `PENDING` clears each bit written 1 and leaves each bit written 0 unchanged; it never sets a bit. [req:IRQ-W1C]
- A write to `CLAIM` acknowledges the source whose number is in `wdata` bits 4 to 0: that source's `PENDING` bit clears and no other bit changes; a number of `N` or more changes nothing. [req:IRQ-ACK]
- A source detected at the same rising edge as a write that clears its bit keeps its `PENDING` bit set, so a high-level source acknowledged while its input is still high stays pending. [req:IRQ-SET-WINS]

### 4.4 The interrupt and the claim

- `irq` is high exactly when some source has both its `PENDING` and its `ENABLE` bit set, for high-level and rising-edge sources alike. [req:IRQ-MASK]
- `irq_id` is the lowest-numbered source whose `PENDING` and `ENABLE` bits are both set, so source 0 has the highest priority, and it is 0 while `irq` is low. [req:IRQ-PRIORITY]
- A read of `CLAIM` returns `irq` in bit 31 and `irq_id` in bits 4 to 0, with every other bit zero. [req:IRQ-CLAIM]
- `irq` and `irq_id` follow the registers with no clock edge, so a source detected at one rising edge drives `irq` until the next. [req:IRQ-LATENCY]
- A write to `ENABLE` that disables the source `irq_id` names moves the claim to the next enabled pending source at the following edge, with no acknowledge. [req:IRQ-RECLAIM]
