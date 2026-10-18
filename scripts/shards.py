"""Split a CI test job across runners, by test file, and check the split.

The `test` and `physical-design` jobs each run as shards on separate runners
(`.github/workflows/ci.yml`). `pytest --shard K/N` (tests/conftest.py) keeps
only the files this module assigns to shard K: whole files, so a module
fixture or a file's own order is never split. Files are placed heaviest first
on the least loaded shard, by the measured seconds in `shard_weights.json`
(a file not listed counts DEFAULT_SECONDS). The weights only balance the
shards: every shard collects the same tests and computes the same assignment,
so each test runs in exactly one shard whatever the numbers say.

Each shard writes a manifest (`--shard-manifest PATH`): the shard, the count
and a digest of everything collected, and the tests it kept. The job that
carries the required check name runs

    python scripts/shards.py MANIFEST.json...

which fails unless the manifests come from one collection, name every shard
once, and together keep every collected test exactly once.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

WEIGHTS = Path(__file__).with_name("shard_weights.json")
DEFAULT_SECONDS = 0.5


def parse(spec: str) -> tuple[int, int]:
    """`K/N` as (K, N), with 1 <= K <= N."""
    try:
        k, n = (int(part) for part in spec.split("/"))
    except ValueError:
        raise ValueError(f"--shard must be K/N, not {spec!r}") from None
    if not 1 <= k <= n:
        raise ValueError(f"--shard {spec}: K must be between 1 and N")
    return k, n


def file_of(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def weights(profile: str, path: Path = WEIGHTS) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if profile not in data:
        raise ValueError(f"no shard weights for {profile!r} in {path.name}")
    return data[profile]


def assign(files: list[str], seconds: dict[str, float], shards: int) -> dict[str, int]:
    """Each file to a shard 1..N: heaviest first onto the least loaded (ties: lower shard; then by name)."""
    loads = [0.0] * shards
    owner = {}
    for name in sorted(set(files), key=lambda f: (-seconds.get(f, DEFAULT_SECONDS), f)):
        shard = min(range(shards), key=lambda s: (loads[s], s))
        loads[shard] += seconds.get(name, DEFAULT_SECONDS)
        owner[name] = shard + 1
    return owner


def select(nodeids: list[str], k: int, n: int, seconds: dict[str, float]) -> list[str]:
    """The tests shard K of N keeps, in collection order."""
    owner = assign([file_of(t) for t in nodeids], seconds, n)
    return [t for t in nodeids if owner[file_of(t)] == k]


def manifest(nodeids: list[str], k: int, n: int, profile: str) -> dict:
    seconds = weights(profile)
    return {
        "profile": profile,
        "shard": k,
        "of": n,
        "collected": len(nodeids),
        "digest": hashlib.sha256("\n".join(nodeids).encode()).hexdigest(),
        "selected": select(nodeids, k, n, seconds),
    }


def problems(manifests: list[dict]) -> list[str]:
    """Why these manifests are not one complete split of one collection (empty when they are)."""
    if not manifests:
        return ["no shard manifests"]
    found = []
    for key in ("profile", "of", "collected", "digest"):
        values = sorted({str(m[key]) for m in manifests})
        if len(values) > 1:
            found.append(f"shards disagree on {key}: {', '.join(values)}")
    n = manifests[0]["of"]
    shards = sorted(m["shard"] for m in manifests)
    if shards != list(range(1, n + 1)):
        found.append(f"expected shards 1..{n} once each, got {shards}")
    seen: dict[str, int] = {}
    for m in manifests:
        for test in m["selected"]:
            if test in seen:
                found.append(f"{test} is in shard {seen[test]} and shard {m['shard']}")
            seen[test] = m["shard"]
    total = sum(len(m["selected"]) for m in manifests)
    if total != manifests[0]["collected"]:
        found.append(f"the shards keep {total} tests, but {manifests[0]['collected']} were collected")
    return found


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: shards.py MANIFEST.json...", file=sys.stderr)
        return 2
    manifests = [json.loads(Path(a).read_text(encoding="utf-8")) for a in argv]
    for m in manifests:
        print(f"shard {m['shard']}/{m['of']} ({m['profile']}): {len(m['selected'])} of {m['collected']} tests")
    found = problems(manifests)
    for problem in found:
        print(problem)
    print("the shards split the collection exactly" if not found else f"{len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
