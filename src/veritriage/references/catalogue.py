"""The built-in offline catalogue of public specification landing pages.

A static table, deliberately. Every entry is a stable, publicly reachable
page for a standard the built-in Knowledge Packs already cite, so resolution
is a lookup and the pipeline stays a pure function of its inputs. Nothing
here opens a socket.

**Order is specificity, most specific first, and the first fragment found in
the source wins.** An earlier draft ranked candidates by fragment length,
which is the wrong proxy and produced two wrong links: "AMBA AXI4-Stream
Protocol Specification" resolved through "amba axi" to the AXI document
because the catalogue had no "axi4-stream" fragment, and "MIPI I3C / NXP
I2C-bus Specification" resolved through the longer "mipi" to the generic MIPI
index instead of the I3C page. Sending an engineer to the wrong standard is
worse than sending them nowhere, so the ordering is now explicit: a narrower
standard is listed above the family it belongs to.

Matching is on a fragment rather than the whole title because packs cite
documents the way engineers write them, and those titles pick up revision
suffixes over time. ``test_every_built_in_citation_resolves_as_expected``
pins the resolution of every source the built-in packs actually cite, so a
new pack or a retitled citation cannot quietly start linking to the wrong
document.
"""

from __future__ import annotations

from veritriage.knowledge.model import Reference
from veritriage.references.registry import ReferenceResolver, register_resolver

_ARM = "https://developer.arm.com/documentation"
_MIPI = "https://www.mipi.org/specifications"
_RISCV = "https://riscv.org/technical/specifications/"

#: (source fragment, landing page), most specific first. Lowercase fragments.
CATALOGUE: tuple[tuple[str, str], ...] = (
    # AMBA. The stream and coherency extensions precede the base protocol.
    ("axi4-stream", f"{_ARM}/ihi0051/latest/"),
    ("axi-stream", f"{_ARM}/ihi0051/latest/"),
    ("axi/ace", f"{_ARM}/ihi0022/latest/"),
    ("amba ace", f"{_ARM}/ihi0022/latest/"),
    ("amba axi", f"{_ARM}/ihi0022/latest/"),
    ("amba ahb", f"{_ARM}/ihi0033/latest/"),
    ("amba apb", f"{_ARM}/ihi0024/latest/"),
    ("amba chi", f"{_ARM}/ihi0050/latest/"),
    # Open interconnects.
    ("open core protocol", "https://www.accellera.org/downloads/standards/ocp"),
    ("wishbone", "https://cdn.opencores.org/downloads/wbspec_b4.pdf"),
    ("tilelink", "https://www.sifive.com/documentation/tilelink/tilelink-spec/"),
    # Chiplet, serial and memory.
    ("ucie", "https://www.uciexpress.org/specifications"),
    ("universal chiplet", "https://www.uciexpress.org/specifications"),
    ("compute express link", "https://computeexpresslink.org/cxl-specification/"),
    ("pci express", "https://pcisig.com/specifications"),
    ("universal serial bus", "https://www.usb.org/documents"),
    ("jedec", "https://www.jedec.org/standards-documents"),
    # MIPI. I3C precedes the family index.
    ("i3c", f"{_MIPI}/i3c-sensor-specification"),
    ("mipi", _MIPI),
    # IEEE. 1800.2 precedes 1800, of which it is a textual prefix.
    ("ieee 802.3", "https://standards.ieee.org/ieee/802.3/"),
    ("ieee 1149.1", "https://standards.ieee.org/ieee/1149.1/"),
    ("ieee 1800.2", "https://standards.ieee.org/ieee/1800.2/"),
    ("ieee 1801", "https://standards.ieee.org/ieee/1801/"),
    ("ieee 1800", "https://standards.ieee.org/ieee/1800/"),
    ("universal verification methodology", "https://www.accellera.org/downloads/standards/uvm"),
    # RISC-V. One landing page covers the ratified set.
    ("risc-v", _RISCV),
)


@register_resolver
class PublicSpecificationCatalogue(ReferenceResolver):
    """Resolves well-known public standards from a static table, offline."""

    resolver_id = "public-catalogue"
    #: Runs last, so any site-specific resolver can claim a source first.
    priority = 900

    def resolve(self, reference: Reference) -> str | None:
        source = reference.source.lower()
        for fragment, uri in CATALOGUE:
            if fragment in source:
                return uri
        return None
