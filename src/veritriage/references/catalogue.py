"""The built-in offline catalogue of public specification landing pages.

A static table, deliberately. Every entry is a stable, publicly reachable
page for a standard the built-in Knowledge Packs already cite by name, so
resolution is a dictionary lookup and the pipeline stays a pure function of
its inputs. Nothing here opens a socket.

Matching is on a distinctive fragment of the source string rather than the
whole title, because packs cite documents the way engineers write them
("AMBA AXI Protocol Specification (IHI 0022)") and those titles pick up
revision suffixes over time. The fragments are specific enough not to
collide: the longest matching fragment wins, so "AMBA AXI-Stream" does not
resolve through the shorter "AMBA AXI" entry.
"""

from __future__ import annotations

from veritriage.knowledge.model import Reference
from veritriage.references.registry import ReferenceResolver, register_resolver

#: Distinctive source fragment (lowercase) -> canonical landing page.
#: Ordered by specificity at match time, not here.
CATALOGUE: dict[str, str] = {
    # AMBA
    "amba axi-stream": "https://developer.arm.com/documentation/ihi0051/latest/",
    "amba ace": "https://developer.arm.com/documentation/ihi0022/latest/",
    "amba axi": "https://developer.arm.com/documentation/ihi0022/latest/",
    "amba ahb": "https://developer.arm.com/documentation/ihi0033/latest/",
    "amba apb": "https://developer.arm.com/documentation/ihi0024/latest/",
    "amba chi": "https://developer.arm.com/documentation/ihi0050/latest/",
    # Open interconnects
    "open core protocol": "https://www.accellera.org/downloads/standards/ocp",
    "wishbone": "https://cdn.opencores.org/downloads/wbspec_b4.pdf",
    "tilelink": "https://www.sifive.com/documentation/tilelink/tilelink-spec/",
    # RISC-V
    "risc-v instruction set manual": "https://riscv.org/technical/specifications/",
    "risc-v": "https://riscv.org/technical/specifications/",
    # Serial and memory
    "pci express": "https://pcisig.com/specifications",
    "compute express link": "https://computeexpresslink.org/cxl-specification/",
    "universal chiplet": "https://www.uciexpress.org/specifications",
    "usb": "https://www.usb.org/documents",
    "jesd": "https://www.jedec.org/standards-documents",
    "mipi": "https://www.mipi.org/specifications",
    "i3c": "https://www.mipi.org/specifications/i3c-sensor-specification",
    "ieee 802.3": "https://standards.ieee.org/ieee/802.3/",
    "ieee 1149.1": "https://standards.ieee.org/ieee/1149.1/",
    # Methodology
    "ieee 1800.2": "https://standards.ieee.org/ieee/1800.2/",
    "ieee 1800": "https://standards.ieee.org/ieee/1800/",
    "ieee 1801": "https://standards.ieee.org/ieee/1801/",
    "universal verification methodology": "https://www.accellera.org/downloads/standards/uvm",
}


@register_resolver
class PublicSpecificationCatalogue(ReferenceResolver):
    """Resolves well-known public standards from a static table, offline."""

    resolver_id = "public-catalogue"
    #: Runs last, so any site-specific resolver can claim a source first.
    priority = 900

    def resolve(self, reference: Reference) -> str | None:
        source = reference.source.lower()
        best: tuple[int, str] | None = None
        for fragment, uri in CATALOGUE.items():
            if fragment in source and (best is None or len(fragment) > best[0]):
                best = (len(fragment), uri)
        return best[1] if best is not None else None
