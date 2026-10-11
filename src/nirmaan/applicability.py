"""When something applies (M48): condition kinds, the facts a reader knows, and the one evaluator.

A :class:`~nirmaan.models.Condition` tests the facts of one registered
condition kind. A kind declares its phase: ``plan`` facts come from the
request, ``run`` facts from the work. Every reader (the planner, the policy's
checks, the runtime's tool runs) builds a :class:`Facts` for its phase and
asks :func:`applies`; nothing tests a requirement's clauses itself.

The rules (docs/UNIFIED_APPLICABILITY.md, section 2.1): a clause of the other
phase is skipped, since it was decided at plan time or cannot be decided yet;
a clause whose facts this reader does not know is skipped; every other clause
must hold. An unregistered kind is an error.

A new kind is one :func:`register_condition_kind` call: the built-in four
are registered the same way.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, MutableMapping
from dataclasses import dataclass
from typing import Any

from nirmaan.models import Condition, ConditionPhase, FileInput
from nirmaan.registry import Registry

#: A fact set as a reader supplies it: the values, or a function computing them only if a clause asks.
FactValue = Iterable[str] | Callable[[], Iterable[str]]


class Facts:
    """What a reader knows when it asks whether something applies.

    Keyword arguments name fact sets (``features=...``, ``produced=...``).
    ``sources`` are the reader's own objects, for kinds that derive their facts
    (``analysis`` and ``requirement`` at plan time; ``state`` and ``task``, or
    ``packet``, at run time).
    """

    def __init__(self, phase: ConditionPhase, sources: dict[str, Any] | None = None, **known: FactValue) -> None:
        self.phase = phase
        self._sources = dict(sources or {})
        self._known = dict(known)
        self._computed: dict[str, frozenset[str]] = {}

    def known(self, name: str) -> frozenset[str] | None:
        """A fact set the reader supplied, computed once; None when it supplied none."""
        if name not in self._known:
            return None
        if name not in self._computed:
            value = self._known[name]
            self._computed[name] = frozenset(value() if callable(value) else value)
        return self._computed[name]

    def source(self, name: str) -> Any:
        """One of the reader's own objects, or None."""
        return self._sources.get(name)


@dataclass(frozen=True)
class ConditionKind:
    """What a ``Condition.on`` can name."""

    name: str
    phase: ConditionPhase
    #: The facts a clause of this kind tests, or None when this reader does not know them yet.
    facts: Callable[[Facts], Iterable[str] | None]
    #: How the work prompt tells a seat about a clause; None says nothing (a plan-time clause is already decided).
    describe: Callable[[Condition], str] | None = None


_KINDS: MutableMapping[str, ConditionKind] = Registry("applicability.kinds")


def register_condition_kind(kind: ConditionKind) -> ConditionKind:
    if kind.name in _KINDS and _KINDS[kind.name] != kind:
        raise ValueError(f"Condition kind {kind.name!r} is already registered")
    _KINDS[kind.name] = kind
    return kind


def unregister_condition_kind(name: str) -> None:
    _KINDS.pop(name, None)


def condition_kind(name: str) -> ConditionKind | None:
    return _KINDS.get(name)


def condition_kinds() -> list[str]:
    return sorted(_KINDS)


def applies(conditions: Iterable[Condition], facts: Facts) -> bool:
    """Whether every clause this reader can decide, in its phase, holds."""
    for clause in conditions:
        kind = _KINDS.get(clause.on)
        if kind is None:
            raise ValueError(f"unknown condition kind {clause.on!r} (registered: {', '.join(condition_kinds())})")
        if kind.phase is not facts.phase or clause.is_unconditional:
            continue
        found = kind.facts(facts)
        if found is not None and not clause.holds(set(found)):
            return False
    return True


def binding_wanted(binding: FileInput, facts: Facts) -> bool:
    """Whether an upstream binding asks for its files: always, unless optional (M41) and none is available.

    ``facts`` know the ``inputs``: the kinds of the approved upstream files available to the task.
    """
    return not binding.optional or applies((Condition(on="inputs", any_of=binding.kinds),), facts)


def describe(conditions: Iterable[Condition]) -> list[str]:
    """What the work prompt says about each clause whose kind has words for it, in order."""
    said = []
    for clause in conditions:
        kind = _KINDS.get(clause.on)
        if kind is not None and kind.describe is not None and not clause.is_unconditional:
            said.append(kind.describe(clause))
    return said


# --- The built-in kinds ------------------------------------------------------------------------------


def _supplied(name: str) -> Callable[[Facts], Iterable[str] | None]:
    return lambda facts: facts.known(name)


def _either(clause: Condition) -> str:
    return " or ".join(clause.any_of or clause.all_of or clause.none_of)


register_condition_kind(ConditionKind("features", ConditionPhase.PLAN, _supplied("features")))
register_condition_kind(ConditionKind(
    "produced", ConditionPhase.RUN, _supplied("produced"),
    lambda c: f"applies only if you produce a {_either(c)} file" if not (c.all_of or c.none_of)
    else f"applies only if what you produce meets {c.model_dump(exclude_defaults=True)}"))
register_condition_kind(ConditionKind(
    "upstream", ConditionPhase.RUN, _supplied("upstream"),
    lambda c: f"applies only to work built on a {_either(c)}" if not (c.all_of or c.none_of)
    else f"applies only to work whose upstream meets {c.model_dump(exclude_defaults=True)}"))
register_condition_kind(ConditionKind(
    "inputs", ConditionPhase.RUN, _supplied("inputs"),
    lambda c: f"applies only when an approved {_either(c)} file is available" if not (c.all_of or c.none_of)
    else f"applies only when the approved inputs meet {c.model_dump(exclude_defaults=True)}"))
