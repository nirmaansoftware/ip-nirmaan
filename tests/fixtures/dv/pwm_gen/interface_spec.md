# Interface specification: `pwm_gen`

A pulse-width modulator, written for this repository in our own words. It is
the block under investigation in the eval case `debug/triage-pwm-gen`; the case
gives the seat the RTL under investigation and the three failing logs.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst` | in | 1 | Reset, active high, synchronous. `pwm` resets low. |
| `duty` | in | 4 | The high time, in clocks. |
| `pwm` | out | 1 | The modulated output. |

`PERIOD` (default 8) is the length of a period in clocks.

- `PWM-PERIOD`: the rising edges of `pwm` are `PERIOD` clocks apart.
- `PWM-DUTY`: in each period `pwm` is high for `duty` consecutive clocks at the
  start of the period and low for the rest. A `duty` of 0 keeps it low.
- `PWM-LATCH`: `duty` is sampled once, at the first clock of a period. A change
  in the middle of a period takes effect in the next period.
