# Triage report: nightly regression

One failing test, `debounce_regress_tb`, one failure bucket. The log has three
`ERROR` lines. Two are the same kind: `clean` changed after `noisy` had
differed from it for fewer than the required four cycles. The third is a
consequence: `clean` changed four times where two settled changes were driven.
The test drives a high bounce, a settled press, a low bounce and a settled
release; the log shows the high bounce did not reach `clean`. The quick repro, `debounce_triage_repro.v`, reads the count register and finds
it not restarted after a low pulse; it reproduces on the RTL under investigation
but is tied to that implementation's register. The failure is open in the
debounce logic and is not classified beyond that.
