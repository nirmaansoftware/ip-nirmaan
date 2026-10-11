# Requirements: `axi4_lite_regs`

The requirements specification for the M44 end-to-end factory project: what
the request "Create an AXI4-Lite register block with a register map, a driver,
scan chains, and a layout on sky130hd" asks for, as its owner baselined it.
Each requirement ends with its tag.

## 1. Function

* Four 32-bit control and status registers behind one AXI4-Lite subordinate port. [req:AXIL-REGS]
* Every register resets to zero and reads back what was written, honouring byte strobes. [req:AXIL-RW]
* An access outside the four registers completes with an error response. [req:AXIL-DECERR]

## 2. Deliverables

* A register map, as data, that the RTL and the driver are both checked against. [req:AXIL-MAP]
* A C driver whose tests pass against the RTL in co-simulation. [req:AXIL-DRIVER]
* Every flop on a scan chain, with stuck-at coverage measured. [req:AXIL-SCAN]
* A routed, extracted layout on sky130hd, DRC and LVS clean, timing met at 100 MHz on every corner. [req:AXIL-LAYOUT]
