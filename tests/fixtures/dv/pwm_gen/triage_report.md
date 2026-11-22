# Triage report: nightly regression

Three failing tests, three buckets, one run of `pwm_gen_regress_tb` each.

1. `pulse_width`: with a duty of 3 the pulse is 4 clocks long, one clock too
   long (`PWM-DUTY`).
2. `period`: the rising edges of `pwm` are 7 clocks apart where `PERIOD` is 8
   (`PWM-PERIOD`).
3. `duty_update`: duty changed from 2 to 6 after the pulse of the period was
   over, and `pwm` rose again in the same period, two clocks later
   (`PWM-LATCH`).

The failures do not overlap: each test judges one thing and the other two
things look right in its log.
