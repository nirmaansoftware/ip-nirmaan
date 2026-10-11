# Driver programming interface: `axi4_lite_regs`

The approved programming interface for the driver of the register block in
`interface_spec.md`. The driver is written to exactly this interface, so that
other software (and other tests) can call it. Register offsets, reset values,
and responses are the interface specification's.

## Files

* `axi4_lite_regs_map.h`: the register map, from the interface specification.
* `axi4_lite_regs_drv.h`: the driver's public declarations (below).
* `axi4_lite_regs_drv.c`: the driver.

## `axi4_lite_regs_map.h`

Defines, as unsigned constants:

* `AXIL_REGS_COUNT`: the number of registers (4).
* `AXIL_REGS_REG0_OFFSET` to `AXIL_REGS_REG3_OFFSET`: each register's byte offset.
* `AXIL_REGS_RESET_VALUE`: the reset value of every register.

## `axi4_lite_regs_drv.h`

Includes `<stdint.h>` and `nirmaan_hal.h`, and declares exactly:

```c
#define AXIL_REGS_OK 0
#define AXIL_REGS_BUS_ERROR (-1)
#define AXIL_REGS_BAD_ARGUMENT (-2)

typedef struct axil_regs {
    const nirmaan_hal *hal;
    unsigned last_response; /* the bus response code of the latest transfer */
} axil_regs;

void axil_regs_init(axil_regs *dev, const nirmaan_hal *hal);
int axil_regs_write(axil_regs *dev, unsigned index, uint32_t value);
int axil_regs_read(axil_regs *dev, unsigned index, uint32_t *value);
int axil_regs_write_byte(axil_regs *dev, unsigned index, unsigned lane, uint8_t value);
int axil_regs_write_offset(axil_regs *dev, uint32_t offset, uint32_t value);
int axil_regs_read_offset(axil_regs *dev, uint32_t offset, uint32_t *value);
```

## Behavior

* `index` is a register index, 0 to `AXIL_REGS_COUNT - 1`; `lane` is a byte
  lane, 0 to 3. An index or lane out of range, or a null pointer, returns
  `AXIL_REGS_BAD_ARGUMENT` with no bus transfer.
* Every other call makes exactly one bus transfer through the HAL, stores the
  transfer's response code in `last_response`, and returns `AXIL_REGS_OK` for
  OKAY and `AXIL_REGS_BUS_ERROR` for any other response. A bus error is never
  swallowed or retried.
* `axil_regs_write_byte` writes one byte lane of a register with the matching
  strobe bit only, leaving the other bytes unchanged.
* `axil_regs_write_offset` and `axil_regs_read_offset` access a raw byte
  offset, for diagnostics; an unmapped offset is a bus error.
