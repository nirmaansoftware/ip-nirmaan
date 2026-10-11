"""The Project Model: a normalized, frozen, content-addressed understanding of
a verification project.

This is the source of truth for Verification Project Intelligence, parallel to
the Knowledge Graph and the Regression Database and deliberately separate from
the Evidence Graph: it describes *what this project is*, not *what happened in a
run*. It is built once from Project Providers, cached, and reused by every
investigation.

All models are frozen. Providers return partial models; ``merge`` unions them
into one (content-addressed, order-independent), ``apply`` fills inferred fields,
and ``seal_project`` stamps the deterministic ``project_id`` and integrity
``fingerprint``. Neither identity nor the fingerprint depends on wall-clock time.

The model never retains raw source text: providers normalize and discard, the
same lossy-by-design law the waveform and engineering layers obey.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Iterable, TypeVar

from pydantic import BaseModel, ConfigDict, Field

_T = TypeVar("_T", bound=BaseModel)


def _union(key, *lists: Iterable[_T]) -> tuple[_T, ...]:
    """Union frozen models across lists, first occurrence of each key wins."""
    seen: dict[object, _T] = {}
    for items in lists:
        for item in items:
            k = key(item)
            if k not in seen:
                seen[k] = item
    return tuple(seen.values())


# --- DUT ---------------------------------------------------------------------


class DesignModule(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    parent: str | None = None
    source_file: str | None = None
    role: str | None = None


class IpBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    kind: str | None = None
    owner: str | None = None
    modules: tuple[str, ...] = ()


class Interface(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    protocol_id: str | None = None
    signals: tuple[str, ...] = ()
    direction: str | None = None
    #: The module whose ports form this interface, when a provider read them (M24).
    module: str | None = None


class ClockDomain(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    roots: tuple[str, ...] = ()


class ResetDomain(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    roots: tuple[str, ...] = ()


class AddressRegion(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    base: str | None = None
    size: str | None = None
    target_ip: str | None = None


class Dut(BaseModel):
    model_config = ConfigDict(frozen=True)
    top: str | None = None
    modules: tuple[DesignModule, ...] = ()
    ip_blocks: tuple[IpBlock, ...] = ()
    interfaces: tuple[Interface, ...] = ()
    clocks: tuple[ClockDomain, ...] = ()
    resets: tuple[ResetDomain, ...] = ()
    address_map: tuple[AddressRegion, ...] = ()

    def merge(self, other: "Dut") -> "Dut":
        return Dut(
            top=self.top or other.top,
            modules=_union(lambda m: m.name, self.modules, other.modules),
            ip_blocks=_union(lambda i: i.name, self.ip_blocks, other.ip_blocks),
            interfaces=_union(lambda i: i.name, self.interfaces, other.interfaces),
            clocks=_union(lambda c: c.name, self.clocks, other.clocks),
            resets=_union(lambda r: r.name, self.resets, other.resets),
            address_map=_union(lambda a: a.name, self.address_map, other.address_map),
        )


# --- Verification environment ------------------------------------------------


class UvmComponent(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    type: str
    parent: str | None = None
    interface: str | None = None


class Vip(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    protocol_id: str | None = None
    interface: str | None = None


class VerificationEnv(BaseModel):
    model_config = ConfigDict(frozen=True)
    components: tuple[UvmComponent, ...] = ()
    ral: str | None = None
    vips: tuple[Vip, ...] = ()
    coverage: tuple[str, ...] = ()
    assertions: tuple[str, ...] = ()

    def merge(self, other: "VerificationEnv") -> "VerificationEnv":
        return VerificationEnv(
            components=_union(
                lambda c: (c.parent, c.name), self.components, other.components
            ),
            ral=self.ral or other.ral,
            vips=_union(lambda v: v.name, self.vips, other.vips),
            coverage=tuple(dict.fromkeys((*self.coverage, *other.coverage))),
            assertions=tuple(dict.fromkeys((*self.assertions, *other.assertions))),
        )


# --- Testbench ---------------------------------------------------------------


class Testbench(BaseModel):
    model_config = ConfigDict(frozen=True)
    tests: tuple[str, ...] = ()
    sequences: tuple[str, ...] = ()
    plusargs: tuple[str, ...] = ()
    config_objects: tuple[str, ...] = ()
    factory_overrides: tuple[str, ...] = ()

    def merge(self, other: "Testbench") -> "Testbench":
        pick = lambda a, b: tuple(dict.fromkeys((*a, *b)))
        return Testbench(
            tests=pick(self.tests, other.tests),
            sequences=pick(self.sequences, other.sequences),
            plusargs=pick(self.plusargs, other.plusargs),
            config_objects=pick(self.config_objects, other.config_objects),
            factory_overrides=pick(self.factory_overrides, other.factory_overrides),
        )


# --- Simulation infrastructure ----------------------------------------------


class LogSource(BaseModel):
    model_config = ConfigDict(frozen=True)
    pattern: str
    origin: str


class GeneratedArtifactKind(BaseModel):
    model_config = ConfigDict(frozen=True)
    glob: str
    ignorable: bool = False


class SimInfra(BaseModel):
    model_config = ConfigDict(frozen=True)
    simulator_vendor: str | None = None
    simulator_version: str | None = None
    waveform_formats: tuple[str, ...] = ()
    log_sources: tuple[LogSource, ...] = ()
    generated_artifacts: tuple[GeneratedArtifactKind, ...] = ()
    formal_flow: str | None = None

    def merge(self, other: "SimInfra") -> "SimInfra":
        return SimInfra(
            simulator_vendor=self.simulator_vendor or other.simulator_vendor,
            simulator_version=self.simulator_version or other.simulator_version,
            waveform_formats=tuple(
                dict.fromkeys((*self.waveform_formats, *other.waveform_formats))
            ),
            log_sources=_union(
                lambda s: (s.pattern, s.origin), self.log_sources, other.log_sources
            ),
            generated_artifacts=_union(
                lambda g: g.glob, self.generated_artifacts, other.generated_artifacts
            ),
            formal_flow=self.formal_flow or other.formal_flow,
        )


# --- Engineering metadata ----------------------------------------------------


class Owner(BaseModel):
    model_config = ConfigDict(frozen=True)
    scope: str
    owner: str
    role: str | None = None


class EngineeringMeta(BaseModel):
    model_config = ConfigDict(frozen=True)
    owners: tuple[Owner, ...] = ()
    repositories: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()
    important_paths: tuple[str, ...] = ()
    ignore_globs: tuple[str, ...] = ()

    def merge(self, other: "EngineeringMeta") -> "EngineeringMeta":
        pick = lambda a, b: tuple(dict.fromkeys((*a, *b)))
        return EngineeringMeta(
            owners=_union(lambda o: (o.scope, o.owner), self.owners, other.owners),
            repositories=pick(self.repositories, other.repositories),
            docs=pick(self.docs, other.docs),
            important_paths=pick(self.important_paths, other.important_paths),
            ignore_globs=pick(self.ignore_globs, other.ignore_globs),
        )


# --- Cross-cutting -----------------------------------------------------------


class LifecyclePhase(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    markers: tuple[str, ...] = ()


class SimulationLifecycle(BaseModel):
    model_config = ConfigDict(frozen=True)
    phases: tuple[LifecyclePhase, ...] = ()

    def merge(self, other: "SimulationLifecycle") -> "SimulationLifecycle":
        # A declared lifecycle wins wholesale; ordering is semantic, not unioned.
        return self if self.phases else other


class LogProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    #: Ordered origin rules; first matching pattern wins during classification.
    rules: tuple[LogSource, ...] = ()

    def merge(self, other: "LogProfile") -> "LogProfile":
        return LogProfile(
            rules=_union(lambda s: (s.pattern, s.origin), self.rules, other.rules)
        )


# --- Root --------------------------------------------------------------------


class ProjectModel(BaseModel):
    """A normalized, frozen, content-addressed verification project model.

    ``extra="allow"`` so a model written by a newer VeriTriage loads without loss
    on an older one, the same forward-compatibility posture as the collab bundle.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    project_id: str = ""
    source_root: str = "."
    built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input_fingerprint: str = Field(
        default="", description="Digest of the sources this model was built from (staleness)."
    )
    provider_versions: dict[str, str] = Field(default_factory=dict)
    fingerprint: str = Field(default="", description="sha256 of the structural content.")

    dut: Dut = Field(default_factory=Dut)
    env: VerificationEnv = Field(default_factory=VerificationEnv)
    testbench: Testbench = Field(default_factory=Testbench)
    sim_infra: SimInfra = Field(default_factory=SimInfra)
    engineering: EngineeringMeta = Field(default_factory=EngineeringMeta)
    lifecycle: SimulationLifecycle = Field(default_factory=SimulationLifecycle)
    log_profile: LogProfile = Field(default_factory=LogProfile)

    @property
    def is_empty(self) -> bool:
        return not (self.dut.modules or self.dut.interfaces or self.env.components)

    def merge(self, other: "ProjectModel") -> "ProjectModel":
        """Union two (partial) models into one; order-independent by content."""
        return ProjectModel(
            source_root=self.source_root if self.source_root != "." else other.source_root,
            input_fingerprint=self.input_fingerprint or other.input_fingerprint,
            provider_versions={**other.provider_versions, **self.provider_versions},
            dut=self.dut.merge(other.dut),
            env=self.env.merge(other.env),
            testbench=self.testbench.merge(other.testbench),
            sim_infra=self.sim_infra.merge(other.sim_infra),
            engineering=self.engineering.merge(other.engineering),
            lifecycle=self.lifecycle.merge(other.lifecycle),
            log_profile=self.log_profile.merge(other.log_profile),
        )


def make_project_id(model: ProjectModel) -> str:
    """Deterministic project ID from structural content only.

    Hashes the source root, DUT top, and the sorted identifying names of
    modules, interfaces, and UVM components: everything that identifies *what
    project this is*, nothing that varies between identical builds.
    """
    parts = [
        model.source_root,
        model.dut.top or "",
        *sorted(m.name for m in model.dut.modules),
        *sorted(i.name for i in model.dut.interfaces),
        *sorted(f"{c.parent}.{c.name}" for c in model.env.components),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"pm-{digest[:12]}"


def _canonical_payload(model: ProjectModel) -> str:
    """Canonical JSON of the structural content, volatile fields blanked."""
    data = model.model_dump(mode="json")
    for volatile in ("project_id", "fingerprint", "built_at", "input_fingerprint"):
        data.pop(volatile, None)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_fingerprint(model: ProjectModel) -> str:
    """sha256 of the model's structural content; unchanged means unmutated."""
    return "sha256:" + hashlib.sha256(_canonical_payload(model).encode("utf-8")).hexdigest()


def seal_project(model: ProjectModel) -> ProjectModel:
    """Return the model with a freshly computed project_id and fingerprint."""
    with_id = model.model_copy(update={"project_id": make_project_id(model)})
    return with_id.model_copy(update={"fingerprint": compute_fingerprint(with_id)})
