"""Read-only containers (M32): project state that cannot be edited in place.

``FrozenDict`` and ``FrozenList`` are ``dict`` and ``list`` subclasses whose
every mutating method raises ``TypeError``. They serialize exactly like plain
ones, and every copy of them (``dict(...)``, ``list(...)``, ``copy.copy``,
``copy.deepcopy``, pickling) is an ordinary, writable container. Standard
library only, so the vocabulary can freeze its own dict fields.
"""

from __future__ import annotations

from typing import Any

_MESSAGE = "project state is read-only outside the task engine; change it through TaskEngine"


def _refuse(*args: Any, **kwargs: Any) -> None:
    raise TypeError(_MESSAGE)


class FrozenDict(dict):
    __setitem__ = __delitem__ = update = pop = popitem = clear = setdefault = __ior__ = _refuse

    def __reduce__(self):  # copy.copy, copy.deepcopy, and pickle all rebuild a plain, writable dict
        return dict, (dict(self),)


class FrozenList(list):
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = sort = reverse = _refuse
    __iadd__ = __imul__ = _refuse

    def __reduce__(self):  # copy.copy, copy.deepcopy, and pickle all rebuild a plain, writable list
        return list, (list(self),)


def frozen(value: Any) -> Any:
    """A read-only version of a dict or list (shallow: the records inside freeze their own fields)."""
    if isinstance(value, (FrozenDict, FrozenList)):
        return value
    if isinstance(value, dict):
        return FrozenDict(value)
    if isinstance(value, list):
        return FrozenList(value)
    return value


def deep_frozen(value: Any) -> Any:
    """Dicts and lists, at every depth, made read-only. Everything else as it is."""
    if isinstance(value, dict):
        return value if isinstance(value, FrozenDict) else FrozenDict({k: deep_frozen(v) for k, v in value.items()})
    if isinstance(value, list):
        return value if isinstance(value, FrozenList) else FrozenList(deep_frozen(v) for v in value)
    return value
