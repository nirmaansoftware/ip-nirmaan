"""One writer for concurrent tasks (M36): model calls in parallel, project state in turn.

``together`` runs a batch of callables, one thread each, under a writer that
holds a single turn. A thread touches project state only while it holds the
turn. It gives the turn up only around work that touches no state, which a
runtime marks with ``outside_writer()`` (``ModelRuntime`` marks its model
call), and when it finishes. The turn always passes to the next unfinished
callable in batch order, cyclically, and waits for it, so the order of every
read and write is a function of the batch alone. ``jobs`` bounds how many
callables may be outside the writer at once; it never changes whose turn it
is. So the same answers to the same prompts give the same state for any
``jobs`` (docs/LOOP_CONCURRENCY.md).

A batch of one runs inline, in the calling thread, with no writer.
"""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Sequence, TypeVar

T = TypeVar("T")

_local = threading.local()


class _Writer:
    def __init__(self, size: int, jobs: int) -> None:
        self._cond = threading.Condition()
        self._slots = threading.Semaphore(jobs)
        self._active = list(range(size))
        self._turn = 0
        self.aborted = threading.Event()

    def _wait(self, index: int) -> None:
        with self._cond:
            self._cond.wait_for(lambda: self._turn == index)

    def _after(self, index: int) -> int:
        later = [i for i in self._active if i > index]
        return later[0] if later else self._active[0]

    def _pass(self, index: int) -> None:
        with self._cond:
            self._turn = self._after(index)
            self._cond.notify_all()

    def _finish(self, index: int) -> None:
        with self._cond:
            nxt = self._after(index)
            self._active.remove(index)
            self._turn = nxt if nxt != index else -1
            self._cond.notify_all()

    @contextmanager
    def outside(self, index: int) -> Iterator[None]:
        # The slot is taken while the turn is still held, so calls are issued in turn order; with one job,
        # they also run one at a time in that order.
        self._slots.acquire()
        self._pass(index)
        _local.outside = True
        try:
            yield
        finally:
            _local.outside = False
            self._slots.release()
            self._wait(index)


@contextmanager
def outside_writer() -> Iterator[None]:
    """Around work that reads and writes no project state (a model call): other tasks take their turns.

    Outside a concurrent batch, or when already outside the writer, it does nothing.
    """
    seat = getattr(_local, "seat", None)
    if seat is None or getattr(_local, "outside", False):
        yield
        return
    writer, index = seat
    with writer.outside(index):
        yield


def stopping() -> bool:
    """True when another callable in this batch failed: finish the step in hand, then start no other."""
    seat = getattr(_local, "seat", None)
    return seat is not None and seat[0].aborted.is_set()


def private(runtime: T) -> T:
    """A shallow copy, so per call state a runtime rebinds on itself stays with one task of a batch."""
    return copy.copy(runtime)


def together(bodies: Sequence[Callable[[], T]], jobs: int = 1) -> list[T]:
    """Run the callables under one writer, at most ``jobs`` outside it at once; their results, in order.

    If any raises, the others finish what they are doing (they see ``stopping()``), and the first
    error in batch order is raised.
    """
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {jobs}")
    if len(bodies) == 1:
        return [bodies[0]()]
    writer = _Writer(len(bodies), jobs)
    results: list[Any] = [None] * len(bodies)
    errors: list[BaseException | None] = [None] * len(bodies)

    def work(index: int) -> None:
        _local.seat = (writer, index)
        try:
            writer._wait(index)
            results[index] = bodies[index]()
        except BaseException as exc:  # raised in this callable's turn, so at a fixed point of the order
            errors[index] = exc
            writer.aborted.set()
        finally:
            _local.seat = None
            writer._finish(index)

    threads = [threading.Thread(target=work, args=(i,), daemon=True) for i in range(len(bodies))]
    for thread in threads:
        thread.start()
    try:
        for thread in threads:
            thread.join()
    except BaseException:  # Ctrl-C: let every step in hand finish and be recorded, then stop
        writer.aborted.set()
        for thread in threads:
            thread.join()
        raise
    for error in errors:
        if error is not None:
            raise error
    return results
