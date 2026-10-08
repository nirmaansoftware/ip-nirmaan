"""Register map vocabulary (M30): a block's registers as data, not a table in prose.

Validated, lowered to a C header or a specification table, and used to
generate a test the RTL must pass. Every register is one ``data_width`` word;
bit fields are not modelled yet.
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


class Unmapped(str, Enum):
    """The response to an address no register holds. Such a write changes no register."""

    SLVERR = "slverr"
    DECERR = "decerr"
    OKAY = "okay"


class Register(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    offset: int = Field(ge=0, description="Byte offset.")
    access: Access = Access.RW
    reset: int = Field(default=0, ge=0)
    description: str = ""


class RegisterMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    block: str = Field(description="The RTL module the map describes.")
    bus: str = Field(description="The bus the registers sit behind, e.g. 'axi4-lite' or 'apb'.")
    addr_width: int = Field(ge=1, description="Byte address width of the bus port.")
    data_width: int = 32
    unmapped: Unmapped = Unmapped.SLVERR
    registers: tuple[Register, ...] = ()
