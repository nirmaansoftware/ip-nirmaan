"""Clock and reset topology, interfaces, protocols, and the address map.

Resolves ``ClockDomain.roots``, ``ResetDomain.roots``, ``Interface.protocol_id``
and ``AddressRegion.target_ip``. Domain membership propagates down the
instantiation hierarchy, which is the one inference this layer makes, and every
such edge is marked ``inferred`` so a reader can tell a declaration from a
deduction.
"""

from __future__ import annotations

from veritriage.design.model import (
    DesignEdge,
    DesignGraph,
    DesignNode,
    DesignRelation,
    NodeKind,
    make_node_id,
)
from veritriage.design.registry import StructureExtractor, register_extractor
from veritriage.project.model import ProjectModel


def _descendants(model: ProjectModel, root: str) -> list[str]:
    """Modules beneath ``root`` in the instantiation hierarchy, cycle-safe."""
    children: dict[str, list[str]] = {}
    for module in model.dut.modules:
        if module.parent:
            children.setdefault(module.parent, []).append(module.name)
    found: list[str] = []
    seen = {root}
    frontier = [root]
    while frontier:
        current = frontier.pop(0)
        for child in sorted(children.get(current, ())):
            if child in seen:
                continue
            seen.add(child)
            found.append(child)
            frontier.append(child)
    return found


@register_extractor
class ClockResetExtractor(StructureExtractor):
    """Clock and reset domains, and which modules live in them."""

    extractor_id = "clock-reset"
    order = 20

    def extract(self, model: ProjectModel, graph: DesignGraph) -> None:
        for domain, kind, relation, field in (
            (model.dut.clocks, NodeKind.CLOCK_DOMAIN, DesignRelation.CLOCKED_BY, "clocks"),
            (model.dut.resets, NodeKind.RESET_DOMAIN, DesignRelation.RESET_BY, "resets"),
        ):
            for entry in domain:
                domain_id = make_node_id(kind, entry.name)
                graph.add_node(
                    DesignNode(
                        id=domain_id,
                        kind=kind,
                        name=entry.name,
                        attributes={"roots": ", ".join(entry.roots)} if entry.roots else {},
                        extracted_by=self.extractor_id,
                    )
                )
                for root in entry.roots:
                    graph.add_edge(
                        DesignEdge(
                            source_id=make_node_id(NodeKind.MODULE, root),
                            target_id=domain_id,
                            relation=relation,
                            rationale=f"dut.{field}[{entry.name}].roots names {root}",
                        )
                    )
                    # Domain membership flows down the hierarchy unless a
                    # descendant declares its own domain. Marked inferred.
                    for child in _descendants(model, root):
                        graph.add_edge(
                            DesignEdge(
                                source_id=make_node_id(NodeKind.MODULE, child),
                                target_id=domain_id,
                                relation=relation,
                                rationale=(
                                    f"{child} is instantiated beneath {root}, which "
                                    f"dut.{field}[{entry.name}].roots declares"
                                ),
                                inferred=True,
                            )
                        )


@register_extractor
class InterfaceExtractor(StructureExtractor):
    """Interfaces, the protocols they speak, and what they connect."""

    extractor_id = "interfaces"
    order = 15  # before verification, which attaches monitors to these

    def extract(self, model: ProjectModel, graph: DesignGraph) -> None:
        for interface in model.dut.interfaces:
            interface_id = make_node_id(NodeKind.INTERFACE, interface.name)
            graph.add_node(
                DesignNode(
                    id=interface_id,
                    kind=NodeKind.INTERFACE,
                    name=interface.name,
                    protocol_id=interface.protocol_id,
                    attributes=(
                        {"signals": ", ".join(interface.signals[:8])}
                        if interface.signals
                        else {}
                    )
                    | ({"direction": interface.direction} if interface.direction else {}),
                    extracted_by=self.extractor_id,
                )
            )
            if interface.protocol_id:
                protocol_id = make_node_id(NodeKind.PROTOCOL, interface.protocol_id)
                graph.add_node(
                    DesignNode(
                        id=protocol_id,
                        kind=NodeKind.PROTOCOL,
                        name=interface.protocol_id,
                        protocol_id=interface.protocol_id,
                        extracted_by=self.extractor_id,
                    )
                )
                graph.add_edge(
                    DesignEdge(
                        source_id=interface_id,
                        target_id=protocol_id,
                        relation=DesignRelation.IMPLEMENTS,
                        rationale=(
                            f"dut.interfaces[{interface.name}].protocol identifies "
                            f"{interface.protocol_id}"
                        ),
                    )
                )
            if interface.module:
                graph.add_edge(
                    DesignEdge(
                        source_id=interface_id,
                        target_id=make_node_id(NodeKind.MODULE, interface.module),
                        relation=DesignRelation.CONNECTS,
                        rationale=(
                            f"dut.interfaces[{interface.name}].module declares {interface.module}"
                        ),
                    )
                )
            # An interface named after the modules it joins connects them, and
            # two modules on one interface communicate. Both are declared by the
            # naming convention the manifest already uses (e.g. "cpu_l2").
            joined = [
                m.name
                for m in model.dut.modules
                if m.name.lower() in interface.name.lower().split("_")
            ]
            for module in joined:
                graph.add_edge(
                    DesignEdge(
                        source_id=interface_id,
                        target_id=make_node_id(NodeKind.MODULE, module),
                        relation=DesignRelation.CONNECTS,
                        rationale=(
                            f"interface {interface.name} names module {module} in its path"
                        ),
                        inferred=True,
                    )
                )
            for left in joined:
                for right in joined:
                    if left >= right:
                        continue
                    graph.add_edge(
                        DesignEdge(
                            source_id=make_node_id(NodeKind.MODULE, left),
                            target_id=make_node_id(NodeKind.MODULE, right),
                            relation=DesignRelation.COMMUNICATES_WITH,
                            rationale=f"both are joined by interface {interface.name}",
                            inferred=True,
                        )
                    )


@register_extractor
class AddressMapExtractor(StructureExtractor):
    """Address regions, register blocks, and what depends on them."""

    extractor_id = "address-map"
    order = 30

    def extract(self, model: ProjectModel, graph: DesignGraph) -> None:
        for region in model.dut.address_map:
            region_id = make_node_id(NodeKind.ADDRESS_REGION, region.name)
            graph.add_node(
                DesignNode(
                    id=region_id,
                    kind=NodeKind.ADDRESS_REGION,
                    name=region.name,
                    attributes={
                        k: v
                        for k, v in (("base", region.base), ("size", region.size))
                        if v
                    },
                    extracted_by=self.extractor_id,
                )
            )
            if region.target_ip:
                graph.add_edge(
                    DesignEdge(
                        source_id=region_id,
                        target_id=make_node_id(NodeKind.IP, region.target_ip),
                        relation=DesignRelation.DEPENDS_ON,
                        rationale=(
                            f"dut.address_map[{region.name}].target_ip names "
                            f"{region.target_ip}"
                        ),
                    )
                )

        if model.env.ral:
            ral_id = make_node_id(NodeKind.REGISTER_BLOCK, model.env.ral)
            graph.add_node(
                DesignNode(
                    id=ral_id,
                    kind=NodeKind.REGISTER_BLOCK,
                    name=model.env.ral,
                    extracted_by=self.extractor_id,
                )
            )
            for region in model.dut.address_map:
                graph.add_edge(
                    DesignEdge(
                        source_id=ral_id,
                        target_id=make_node_id(NodeKind.ADDRESS_REGION, region.name),
                        relation=DesignRelation.DEPENDS_ON,
                        rationale=(
                            f"the register model {model.env.ral} addresses "
                            f"{region.name} in the address map"
                        ),
                        inferred=True,
                    )
                )
