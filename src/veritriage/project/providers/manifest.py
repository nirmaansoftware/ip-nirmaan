"""Canonical project manifest provider (tool-independent JSON).

The reference contract: the ``*.vproj.json`` format any project or CI can export
to describe its verification structure without VeriTriage learning a source
language or build tool. It is the full-fidelity path (declares every capability)
and the increment that ships first; RTL, UVM, build, and regression providers
land additively behind the same interface.

Schema (`*.vproj.json`, every field optional):

    {
      "project": {"name": "...", "source_root": "."},
      "dut": {"top": "...", "modules": [...], "ips": [...], "interfaces": [...],
              "clocks": [...], "resets": [...], "address_map": [...]},
      "env": {"components": [...], "ral": "...", "vips": [...]},
      "testbench": {"tests": [...], "sequences": [...], "plusargs": [...]},
      "sim_infra": {"simulator": {"vendor": "...", "version": "..."},
                    "waveform_formats": [...], "log_sources": [...],
                    "generated_artifacts": [...]},
      "lifecycle": {"phases": [{"name": "...", "markers": [...]}]},
      "engineering": {"owners": [{"scope": "...", "owner": "..."}]}
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from veritriage.project.model import (
    AddressRegion,
    ClockDomain,
    DesignModule,
    Dut,
    EngineeringMeta,
    GeneratedArtifactKind,
    Interface,
    IpBlock,
    LifecyclePhase,
    LogProfile,
    LogSource,
    Owner,
    ProjectModel,
    ResetDomain,
    SimInfra,
    SimulationLifecycle,
    Testbench,
    VerificationEnv,
    Vip,
    UvmComponent,
)
from veritriage.project.providers.base import (
    ProjectCapability,
    ProjectProvider,
    ProjectProviderError,
)
from veritriage.project.providers.registry import register_project_provider

#: Filename patterns the manifest entry claims.
MANIFEST_PATTERNS = ("*.vproj.json", "project.vproj.json")

#: Bumped when the manifest interpretation changes.
MANIFEST_PROVIDER_VERSION = "1.0.0"


def _str(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _tuple(values: Any) -> tuple[str, ...]:
    return tuple(str(v) for v in (values or []))


def load_manifest(path: Path) -> ProjectModel:
    """Parse one ``*.vproj.json`` file into a normalized ProjectModel.

    Raises:
        ProjectProviderError: If the file is not valid manifest JSON.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProjectProviderError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectProviderError(f"{path}: expected a JSON object at the top level")

    project = data.get("project") or {}
    dut_raw = data.get("dut") or {}
    env_raw = data.get("env") or {}
    tb_raw = data.get("testbench") or {}
    sim_raw = data.get("sim_infra") or {}
    life_raw = data.get("lifecycle") or {}
    eng_raw = data.get("engineering") or {}

    dut = Dut(
        top=_str(dut_raw.get("top")),
        modules=tuple(
            DesignModule(
                name=str(m["name"]),
                parent=_str(m.get("parent")),
                source_file=_str(m.get("source_file")),
                role=_str(m.get("role")),
            )
            for m in dut_raw.get("modules", [])
        ),
        ip_blocks=tuple(
            IpBlock(
                name=str(i["name"]),
                kind=_str(i.get("kind")),
                owner=_str(i.get("owner")),
                modules=_tuple(i.get("modules")),
            )
            for i in dut_raw.get("ips", [])
        ),
        interfaces=tuple(
            Interface(
                name=str(f["name"]),
                protocol_id=_str(f.get("protocol")),
                signals=_tuple(f.get("signals")),
                direction=_str(f.get("direction")),
                module=_str(f.get("module")),
            )
            for f in dut_raw.get("interfaces", [])
        ),
        clocks=tuple(
            ClockDomain(name=str(c["name"]), roots=_tuple(c.get("roots")))
            for c in dut_raw.get("clocks", [])
        ),
        resets=tuple(
            ResetDomain(name=str(r["name"]), roots=_tuple(r.get("roots")))
            for r in dut_raw.get("resets", [])
        ),
        address_map=tuple(
            AddressRegion(
                name=str(a["name"]),
                base=_str(a.get("base")),
                size=_str(a.get("size")),
                target_ip=_str(a.get("target_ip")),
            )
            for a in dut_raw.get("address_map", [])
        ),
    )

    env = VerificationEnv(
        components=tuple(
            UvmComponent(
                name=str(c["name"]),
                type=str(c.get("type", "component")),
                parent=_str(c.get("parent")),
                interface=_str(c.get("interface")),
            )
            for c in env_raw.get("components", [])
        ),
        ral=_str((env_raw.get("ral") or {}).get("name") if isinstance(env_raw.get("ral"), dict) else env_raw.get("ral")),
        vips=tuple(
            Vip(
                name=str(v["name"]),
                protocol_id=_str(v.get("protocol")),
                interface=_str(v.get("interface")),
            )
            for v in env_raw.get("vips", [])
        ),
        coverage=_tuple(env_raw.get("coverage")),
        assertions=_tuple(env_raw.get("assertions")),
    )

    testbench = Testbench(
        tests=_tuple(tb_raw.get("tests")),
        sequences=_tuple(tb_raw.get("sequences")),
        plusargs=_tuple(tb_raw.get("plusargs")),
        config_objects=_tuple(tb_raw.get("config_objects")),
        factory_overrides=_tuple(tb_raw.get("factory_overrides")),
    )

    simulator = sim_raw.get("simulator") or {}
    log_sources = tuple(
        LogSource(pattern=str(s["pattern"]), origin=str(s["origin"]))
        for s in sim_raw.get("log_sources", [])
    )
    sim_infra = SimInfra(
        simulator_vendor=_str(simulator.get("vendor")),
        simulator_version=_str(simulator.get("version")),
        waveform_formats=_tuple(sim_raw.get("waveform_formats")),
        log_sources=log_sources,
        generated_artifacts=tuple(
            GeneratedArtifactKind(
                glob=str(g["glob"]), ignorable=bool(g.get("ignorable", False))
            )
            for g in sim_raw.get("generated_artifacts", [])
        ),
        formal_flow=_str(sim_raw.get("formal_flow")),
    )

    lifecycle = SimulationLifecycle(
        phases=tuple(
            LifecyclePhase(name=str(p["name"]), markers=_tuple(p.get("markers")))
            for p in life_raw.get("phases", [])
        )
    )
    # The declared log sources double as the log-origin profile.
    log_profile = LogProfile(rules=log_sources)

    engineering = EngineeringMeta(
        owners=tuple(
            Owner(scope=str(o["scope"]), owner=str(o["owner"]), role=_str(o.get("role")))
            for o in eng_raw.get("owners", [])
        ),
        repositories=_tuple(eng_raw.get("repositories")),
        docs=_tuple(eng_raw.get("docs")),
        important_paths=_tuple(eng_raw.get("important_paths")),
        ignore_globs=_tuple(eng_raw.get("ignore_globs")),
    )

    return ProjectModel(
        source_root=_str(project.get("source_root")) or ".",
        provider_versions={VprojManifestProvider.name: MANIFEST_PROVIDER_VERSION},
        dut=dut,
        env=env,
        testbench=testbench,
        sim_infra=sim_infra,
        engineering=engineering,
        lifecycle=lifecycle,
        log_profile=log_profile,
    )


@register_project_provider
class VprojManifestProvider(ProjectProvider):
    """Reads canonical ``*.vproj.json`` project manifests at the collection root."""

    name = "project_manifest"
    source = "manifest"
    capabilities = frozenset(ProjectCapability)  # canonical: declares everything

    @classmethod
    def available(cls, root: Path) -> bool:
        return bool(cls._manifests(root))

    def collect(self, root: Path) -> ProjectModel:
        merged = ProjectModel(source_root=str(root))
        for path in self._manifests(root):
            merged = merged.merge(load_manifest(path))
        return merged

    @staticmethod
    def _manifests(root: Path) -> list[Path]:
        # A directory root is globbed; a manifest file path is claimed directly.
        if root.is_file() and any(root.match(p) for p in MANIFEST_PATTERNS):
            return [root]
        if not root.is_dir():
            return []
        found: list[Path] = []
        for pattern in MANIFEST_PATTERNS:
            found.extend(sorted(root.glob(pattern)))
        return found
