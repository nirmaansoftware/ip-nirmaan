<!-- A mutant that is wrong on purpose (RX-E2): interface_spec.md with one change. One requirement carries the ID of another, so the specification tags one ID twice and no plan that cites each requirement once can match it. Everything else is identical. -->

# Interface specification: `tick_timer`

A down-counting timer that raises an interrupt when its count runs out. Software
writes a reload value, starts the timer, and the count falls by one at each
clock edge until it reaches zero. In one-shot mode the timer then stops; in
periodic mode it reloads and runs again. An expired flag records that the count
ran out and is cleared by writing a one to it; the interrupt line is that flag
gated by an interrupt enable bit.

This is the approved specification of the block the verification eval cases
`dv/coverage-tick-timer` and `dv/plan-tick-timer` verify. It was written for
this repository in our own words; the load, start, expire and clear set is the
usual shape of a small timer and copies no other document.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `W` | 16 | Width of the count and the reload value in bits, 4 to 32. |

- The block works for every `W` from 4 to 32, and bits `W` and up of the `LOAD` and `COUNT` registers read as zero; a write to `LOAD` ignores them. [req:TMR-PARAM]

## 2. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `we` | in | 1 | Register write: the write takes effect at the rising edge where `we` is high. |
| `addr` | in | 2 | Register number, for reads and writes. |
| `wdata` | in | 32 | Write data. |
| `rdata` | out | 32 | Read data: the register `addr` selects, at all times. |
| `irq` | out | 1 | Interrupt to the processor, active high, level sensitive. |

## 3. Register map

Every register is 32 bits.

| `addr` | Name | Access | Meaning |
|---|---|---|---|
| 0 | `CTRL` | read/write | bit 0 `EN` runs the timer; bit 1 `MODE` is 1 for periodic and 0 for one-shot; bit 2 `IE` enables the interrupt; other bits read as zero |
| 1 | `LOAD` | read/write | the reload value, `W` bits |
| 2 | `COUNT` | read only | the count now, `W` bits; a write changes nothing |
| 3 | `STATUS` | read, write 1 to clear | bit 0 `EXPIRED`; other bits read as zero |

## 4. Behaviour

### 4.1 Reset and registers

- While `rst_n` is low at a rising edge of `clk`, `CTRL`, `LOAD`, `COUNT` and `STATUS` clear to zero. [req:TMR-RESET]
- A write to `CTRL` stores `wdata` bits 2 to 0 in it, and a write to `LOAD` stores `wdata` bits `W-1` to 0 in it. [req:TMR-REG-RW]
- A read never changes any register; `rdata` follows `addr` with no clock edge. [req:TMR-READ]

### 4.2 Counting

- At a rising edge where a write to `CTRL` sets `EN` and `EN` was 0, the count loads the `LOAD` value. [req:TMR-START]
- At a rising edge where `EN` is 1 and the count is not zero, and no write to `CTRL` takes place, the count falls by one. [req:TMR-COUNT]
- A write to `CTRL` takes the place of that edge's count step: at that edge the count does not fall and the timer does not expire, whatever the count was. [req:TMR-WRITE-WINS]
- A write to `CTRL` that clears `EN` stops the timer and the count keeps its value. [req:TMR-STOP]
- A write to `LOAD` does not change the count: the new value is used at the next start or periodic reload. [req:TMR-LOAD-LATE]

### 4.3 Expiry

- At a rising edge where `EN` is 1 and the count is zero, and no write to `CTRL` takes place, the timer expires: `EXPIRED` is set. [req:TMR-EXPIRE]
- In periodic mode an expiry also loads the count with the `LOAD` value, and `EN` stays 1. [req:TMR-EXPIRE]
- In one-shot mode an expiry also clears `EN`, and the count stays zero until the next start. [req:TMR-ONESHOT]

### 4.4 The flag and the interrupt

- A write to `STATUS` with bit 0 set clears `EXPIRED`, and with bit 0 clear changes nothing; it never sets the flag. [req:TMR-W1C]
- A timer that expires at the same rising edge as a write that clears `EXPIRED` keeps `EXPIRED` set. [req:TMR-SET-WINS]
- `irq` is high exactly when `EXPIRED` and `IE` are both 1, in one-shot and periodic mode alike; it follows the registers with no clock edge. [req:TMR-IRQ]
