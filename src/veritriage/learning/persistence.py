"""The Learning Store: a rebuildable, derived view over recorded history.

A separate SQLite file from the regression database on purpose. The regression
database is the immutable record of what happened; the learning store is a
derived projection of it. Deleting the learning store loses nothing that cannot
be recomputed, and returns the platform to exact pre-M13 behavior, which is a
testable property rather than a claim.

Standard library only, matching `storage/sqlite.py`. Artifacts are stored as
complete JSON with their kind, so the typed subclass is reconstructed on read
and nothing is summarized away.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from veritriage.models import (
    AgentReliability,
    EvidencePattern,
    HypothesisHistory,
    InvestigationPattern,
    LearningArtifact,
    LearningStatistics,
    ProjectProfile,
    ProtocolStatistics,
    RecommendationOutcome,
    RuleGap,
)

#: Artifact kind -> the model that reconstructs it. A learner shipping a new
#: kind registers it here (or stores as the plain base, which still round-trips).
ARTIFACT_TYPES: dict[str, type[LearningArtifact]] = {
    "investigation_pattern": InvestigationPattern,
    "evidence_pattern": EvidencePattern,
    "agent_reliability": AgentReliability,
    "project_profile": ProjectProfile,
    "protocol_statistics": ProtocolStatistics,
    "recommendation_outcome": RecommendationOutcome,
    "hypothesis_history": HypothesisHistory,
    "rule_gap": RuleGap,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    key         TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    record      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts (kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_key ON artifacts (key);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _load(kind: str, blob: str) -> LearningArtifact:
    model = ARTIFACT_TYPES.get(kind, LearningArtifact)
    return model.model_validate_json(blob)


class LearningStore:
    """Persistent home for derived learning artifacts."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "LearningStore":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- Writing ------------------------------------------------------------

    def replace_all(
        self,
        artifacts: list[LearningArtifact],
        corpus_size: int = 0,
        feedback_count: int = 0,
        generated_at: str = "",
    ) -> None:
        """Atomically replace the whole artifact set.

        Wholesale replacement rather than incremental update, because learning
        is a pure function of history: a rebuild is the normal path, and a
        partial write would let stale artifacts outlive the records that
        justified them.
        """
        with self._conn:
            self._conn.execute("DELETE FROM artifacts")
            self._conn.executemany(
                "INSERT INTO artifacts (artifact_id, kind, key, updated_at, record) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        a.artifact_id,
                        a.kind,
                        a.key,
                        a.updated_at,
                        a.model_dump_json(),
                    )
                    for a in artifacts
                ],
            )
            self._conn.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [
                    ("corpus_size", str(corpus_size)),
                    ("feedback_count", str(feedback_count)),
                    ("generated_at", generated_at),
                ],
            )

    def clear(self) -> None:
        """Forget everything learned. History itself is untouched."""
        with self._conn:
            self._conn.execute("DELETE FROM artifacts")
            self._conn.execute("DELETE FROM meta")

    # --- Reading ------------------------------------------------------------

    def all_artifacts(self) -> list[LearningArtifact]:
        rows = self._conn.execute(
            "SELECT kind, record FROM artifacts ORDER BY artifact_id"
        ).fetchall()
        return [_load(row["kind"], row["record"]) for row in rows]

    def by_kind(self, kind: str) -> list[LearningArtifact]:
        rows = self._conn.execute(
            "SELECT kind, record FROM artifacts WHERE kind = ? ORDER BY artifact_id",
            (kind,),
        ).fetchall()
        return [_load(row["kind"], row["record"]) for row in rows]

    def by_key(self, kind: str, key: str) -> LearningArtifact | None:
        row = self._conn.execute(
            "SELECT kind, record FROM artifacts WHERE kind = ? AND key = ?",
            (kind, key),
        ).fetchone()
        return _load(row["kind"], row["record"]) if row else None

    def get(self, artifact_id: str) -> LearningArtifact | None:
        row = self._conn.execute(
            "SELECT kind, record FROM artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone()
        return _load(row["kind"], row["record"]) if row else None

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])

    def meta(self, key: str, default: str = "") -> str:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def statistics(self, learners: list[str] | None = None) -> LearningStatistics:
        """The shape of what has been learned so far."""
        rows = self._conn.execute(
            "SELECT kind, COUNT(*) AS n FROM artifacts GROUP BY kind ORDER BY kind"
        ).fetchall()
        return LearningStatistics(
            corpus_size=int(self.meta("corpus_size", "0") or 0),
            feedback_count=int(self.meta("feedback_count", "0") or 0),
            artifacts_by_kind={row["kind"]: int(row["n"]) for row in rows},
            learners=sorted(learners or []),
            generated_at=self.meta("generated_at"),
        )

    def export(self) -> str:
        """Every artifact as canonical JSON; used by tests to pin determinism."""
        return json.dumps(
            [a.model_dump(mode="json") for a in self.all_artifacts()],
            sort_keys=True,
            separators=(",", ":"),
        )
