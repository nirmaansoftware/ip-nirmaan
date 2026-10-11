"""Freezing project state (M32): the engine holds a state nothing can edit in place.

The engine freezes a state when it takes it over and every container it
commits, which is what lets P10 compare states by identity instead of hashing
them. The containers themselves are in ``nirmaan.models.frozen``.
"""

from __future__ import annotations

from nirmaan.models import ProjectState
from nirmaan.models.frozen import FrozenDict, FrozenList, deep_frozen

#: The ProjectState fields that hold containers.
CONTAINER_FIELDS = tuple(name for name, info in ProjectState.model_fields.items()
                         if getattr(info.annotation, "__origin__", None) in (dict, list))


def freeze_state(state: ProjectState) -> ProjectState:
    """The same state with every top-level container read-only. A no-op on one already frozen."""
    updates = {name: (FrozenDict if isinstance(getattr(state, name), dict) else FrozenList)(getattr(state, name))
               for name in CONTAINER_FIELDS if not isinstance(getattr(state, name), (FrozenDict, FrozenList))}
    return state.model_copy(update=updates) if updates else state


__all__ = ["CONTAINER_FIELDS", "FrozenDict", "FrozenList", "deep_frozen", "freeze_state"]
