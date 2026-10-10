# v1.22.0 - the structural review and the M29 parts

v1.22.0 is the one version bump for everything merged after v1.21.0: the
structural review and its seven milestones (#37 seat evaluation, an M27 part;
#41 M28 tool contracts; #48 engineering records, an M29 part; #52 M30 register
map; #53 M31 model selection and accounting; #54 M32 scalable state; #55 M33
learning proposals) and the parallel M29 parts (#46 the unattended loop, #47
verification plans, #49 RISC-V, #50 DFT, #51 the remaining RTL gates). The
standard local run is 1424 tests with 3 skipped: the real OpenROAD tests, which
run in CI's `physical-design` job. No live-model evaluation has run yet: this
machine has no Anthropic credentials (`nirmaan eval run --runtime anthropic`
once one is set). It ran after the release on the owner's plan through the claude-code runtime
(#57); see that entry below.
