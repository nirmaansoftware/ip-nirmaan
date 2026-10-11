"""Scoped registries (M49): every extension point is a ``Registry`` in one ``Registries`` context object.

A ``Registry`` is a named handle declared where a module-level dict used to be.
It is a mapping, so the code that read and wrote the dict is unchanged, but it
stores nothing itself: each operation goes to the current ``Registries``.

The process has one default ``Registries``. A scoped one layers over another:
lookups fall through to the layer below, writes and removals stay in its own
layer, so a scope cannot remove a default, and what it registers is gone
when the scope is no longer used. The current instance is a
ContextVar; ``runtime.writer.together`` copies the context into each thread it
starts, so M36's ``--jobs`` threads see the scope of the run that started them.
A write made while a module is being imported goes to the defaults, whatever
scope is current: import-time registration is process-wide.

See docs/SCOPED_REGISTRIES.md.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterator, MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_KINDS: dict[str, "Registry"] = {}
_UNSET: Any = object()


class Registries:
    """Every registry's entries for one scope: a layer per registry name, over an optional parent."""

    _default: "Registries | None" = None

    def __init__(self, parent: "Registries | None" = _UNSET) -> None:
        self.parent = Registries.default() if parent is _UNSET else parent
        self._layers: dict[str, dict[Any, Any]] = {}
        self._lock = threading.RLock()

    # --- Which instance is current --------------------------------------------------------------

    @classmethod
    def default(cls) -> "Registries":
        """The process's defaults: what every module-level ``register_*`` writes outside any scope."""
        if cls._default is None:
            cls._default = cls(parent=None)
        return cls._default

    @classmethod
    def current(cls) -> "Registries":
        scope = _CURRENT.get()
        return scope if scope is not None else cls.default()

    @classmethod
    def kinds(cls) -> list[str]:
        """The name of every declared registry."""
        return sorted(_KINDS)

    @classmethod
    @contextmanager
    def scoped(cls) -> Iterator["Registries"]:
        """A new scope over the current one, current for the duration of the block."""
        with cls(parent=cls.current()).using() as scope:
            yield scope

    @contextmanager
    def using(self) -> Iterator["Registries"]:
        """Make this instance current for the block (a scope kept per organization is entered this way)."""
        token = _CURRENT.set(self)
        try:
            yield self
        finally:
            _CURRENT.reset(token)

    # --- Entries ----------------------------------------------------------------------------------

    def _chain(self) -> list["Registries"]:
        """This instance and its parents, the defaults last."""
        chain, scope = [], self
        while scope is not None:
            chain.append(scope)
            scope = scope.parent
        return chain

    def lookup(self, name: str, key: Any) -> Any:
        for scope in self._chain():
            layer = scope._layers.get(name)
            if layer is not None and key in layer:
                return layer[key]
        raise KeyError(key)

    def keys(self, name: str) -> list[Any]:
        """A snapshot of the keys, the defaults' first, each once."""
        keys: dict[Any, None] = {}
        for scope in reversed(self._chain()):
            with scope._lock:
                keys.update(dict.fromkeys(scope._layers.get(name, ())))
        return list(keys)

    def write(self, name: str, key: Any, value: Any) -> None:
        with self._lock:
            self._layers.setdefault(name, {})[key] = value

    def remove(self, name: str, key: Any) -> Any:
        """Remove from this instance's own layer only; KeyError if it is not there."""
        with self._lock:
            return self._layers.get(name, {}).pop(key)


_CURRENT: ContextVar[Registries | None] = ContextVar("nirmaan_registries", default=None)


def _importing() -> bool:
    """True while any frame on the stack is the body of a module still being imported."""
    frame = sys._getframe(2)
    while frame is not None:
        if frame.f_code.co_name == "<module>":
            spec = frame.f_globals.get("__spec__")
            if spec is not None and getattr(spec, "_initializing", False):
                return True
        frame = frame.f_back
    return False


def _target() -> Registries:
    return Registries.default() if _importing() else Registries.current()


class Registry(MutableMapping):
    """One extension point, by name. Reads see the current scope over the defaults; writes go to the scope."""

    def __init__(self, name: str) -> None:
        if name in _KINDS:
            raise ValueError(f"A registry named {name!r} is already declared")
        self.name = name
        _KINDS[name] = self

    def __getitem__(self, key: Any) -> Any:
        return Registries.current().lookup(self.name, key)

    def __setitem__(self, key: Any, value: Any) -> None:
        _target().write(self.name, key, value)

    def __delitem__(self, key: Any) -> None:
        _target().remove(self.name, key)

    def __iter__(self) -> Iterator[Any]:
        return iter(Registries.current().keys(self.name))

    def __len__(self) -> int:
        return len(Registries.current().keys(self.name))

    def __contains__(self, key: object) -> bool:
        try:
            self[key]
        except KeyError:
            return False
        return True

    def pop(self, key: Any, default: Any = _UNSET) -> Any:
        """Remove from the current scope's own layer (from the defaults outside any scope)."""
        try:
            return _target().remove(self.name, key)
        except KeyError:
            if default is _UNSET:
                raise
            return default

    def __repr__(self) -> str:
        return f"Registry({self.name!r})"
