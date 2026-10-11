"""Register map vocabulary (M30): a block's registers as data, not a table in prose.

Validated, lowered to a C header or a specification table, and used to
generate a test the RTL must pass. A register is one ``data_width`` word,
optionally divided into bit fields (M41, docs/REGISTER_MAP_ADOPTION.md).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Access(str, Enum):
    #: Every bit is writable and reads back what was written.
    RW = "rw"
    #: Writes are ignored; reads return the reset value.
    RO = "ro"
    #: Writes are accepted; what a read returns is not defined, so it is never checked.
    WO = "wo"
    #: Reads the bits; writing 1 clears a bit, writing 0 leaves it (M41).
    W1C = "w1c"


class Unmapped(str, Enum):
    """The response to an address no register holds. Such a write changes no register."""

    SLVERR = "slverr"
    DECERR = "decerr"
    OKAY = "okay"


class BitField(BaseModel):
    """Bits ``msb`` down to ``lsb`` of a register (M41). Bits no field holds read zero and ignore writes."""

    model_config = ConfigDict(frozen=True)

    name: str
    lsb: int = Field(ge=0)
    msb: int | None = Field(default=None, ge=0, description="Defaults to lsb: a one-bit field.")
    access: Access = Access.RW
    reset: int = Field(default=0, ge=0, description="The field's own value, not shifted.")
    description: str = ""

    @property
    def high(self) -> int:
        return self.lsb if self.msb is None else self.msb

    @property
    def width(self) -> int:
        return self.high - self.lsb + 1

    @property
    def mask(self) -> int:
        """The field's bits, in place."""
        return ((1 << max(self.width, 0)) - 1) << self.lsb


class Register(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    offset: int = Field(ge=0, description="Byte offset.")
    #: With fields, the fields' accesses govern the bits and this must stay ``rw``.
    access: Access = Access.RW
    #: With fields, this must equal the fields' resets put in place.
    reset: int = Field(default=0, ge=0)
    description: str = ""
    fields: tuple[BitField, ...] = ()


class RegisterMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    block: str = Field(description="The RTL module the map describes.")
    bus: str = Field(description="The bus the registers sit behind, e.g. 'axi4-lite' or 'apb'.")
    addr_width: int = Field(ge=1, description="Byte address width of the bus port.")
    data_width: int = 32
    unmapped: Unmapped = Unmapped.SLVERR
    registers: tuple[Register, ...] = ()
