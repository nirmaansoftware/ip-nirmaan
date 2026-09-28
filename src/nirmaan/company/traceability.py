"""The engineering-graph vocabulary (M24): how artifacts link to design, and what proves what.

Two tables, both data. ``nirmaan.engineering`` reads them and names no kind
itself; ``register_link_kind`` and ``register_item_kind`` there add or replace
an entry without a code change (the crown-jewel test proves it).

A **link kind** says which artifact kinds link to which Design Graph nodes.
Links are never recorded: each is derived from the artifact's digest-checked
file, parsed by VeriTriage. The walk starts from the modules the file defines;
each step follows a Design Graph relation (a leading ``<`` follows it
backwards). With no steps, the defined modules themselves are the targets;
with steps, only nodes reached by a step are.

An **item kind** says which tools' runs can prove a verification item of that
kind. A run counts only when it names the item's file, succeeded, and is cited
by substantiated tool-run evidence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkKind:
    id: str
    artifact_kinds: tuple[str, ...]
    node_kinds: tuple[str, ...]
    walk: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class ItemKind:
    id: str
    tools: tuple[str, ...]
    description: str = ""


LINK_KINDS: list[LinkKind] = [
    LinkKind("defines", ("rtl_source",), ("module",),
             description="An RTL file links to the modules it defines."),
    LinkKind("exercises", ("testbench",), ("module", "interface"), ("instantiates", "<connects"),
             description="A testbench links to the modules it instantiates and the interfaces of those modules."),
]

ITEM_KINDS: list[ItemKind] = [
    ItemKind("test", ("simulator.run", "test.run"),
             "A test or self-check, proven by a passing simulation of the file that holds it."),
    ItemKind("assertion", ("formal.run", "simulator.run"),
             "An assertion, proven by formal or never fired in a passing simulation."),
    ItemKind("coverage_point", ("coverage.read",),
             "A cover point, proven only by a coverage measurement."),
]
