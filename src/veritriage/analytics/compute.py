"""Aggregations and clustering over the regression database."""

from __future__ import annotations

from collections import Counter as TallyCounter
from collections import defaultdict

from veritriage.analytics.models import AnalyticsReport, Counter, DailyPoint, FailureCluster
from veritriage.history.record import RegressionRecord
from veritriage.learning.corpus import Corpus
from veritriage.learning.learners.gaps import compute_rule_gaps
from veritriage.similarity import cosine
from veritriage.storage import RegressionStore

#: Signature groups merge into one cluster from this embedding similarity up.
_CLUSTER_THRESHOLD = 0.7
_TOP_N = 10


class RegressionAnalytics:
    """Computes the AnalyticsReport the dashboard and CLI render."""

    def __init__(self, store: RegressionStore) -> None:
        self._store = store

    def compute(self) -> AnalyticsReport:
        records = self._store.all_records()
        # The same aggregation the rule-gap learner persists, computed here
        # directly from history so the dashboard needs no learning store.
        gaps = compute_rule_gaps(Corpus(records, self._store.all_feedback()))
        failures = [r for r in records if r.is_failure]

        modules: TallyCounter[str] = TallyCounter()
        categories: TallyCounter[str] = TallyCounter()
        assertions: TallyCounter[str] = TallyCounter()
        signals: TallyCounter[str] = TallyCounter()
        recommendations: TallyCounter[str] = TallyCounter()
        confidence: TallyCounter[str] = TallyCounter()
        daily: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        heatmap: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for record in records:
            day = record.created_at.date().isoformat()
            daily[day][0] += 1
            if record.is_failure:
                daily[day][1] += 1
        for record in failures:
            categories[record.report.classification.category.display_name] += 1
            bucket = min(record.confidence // 10 * 10, 90)
            confidence[f"{bucket}-{bucket + 9}%"] += 1
            for module in record.signature.modules:
                modules[module] += 1
                heatmap[module][record.report.classification.category.display_name] += 1
            for assertion in record.signature.assertions:
                assertions[assertion] += 1
            if record.report.reasoning is not None:
                for signal in record.report.reasoning.signals:
                    signals[signal.name] += 1
                for rec in record.report.reasoning.recommendations:
                    recommendations[rec.action] += 1

        def top(tally: TallyCounter[str], total: int) -> list[Counter]:
            return [
                Counter(label=label, count=count, share=count / total if total else 0.0)
                for label, count in tally.most_common(_TOP_N)
            ]

        n_fail = len(failures)
        return AnalyticsReport(
            rule_gaps=gaps,
            total_runs=len(records),
            total_failures=n_fail,
            unknown_failures=sum(
                1 for r in failures if r.classification == "unknown_failure"
            ),
            distinct_signatures=len({r.signature.digest for r in failures}),
            failing_modules=top(modules, n_fail),
            failure_categories=top(categories, n_fail),
            assertion_hotspots=top(assertions, n_fail),
            signal_frequency=top(signals, n_fail),
            repeated_recommendations=top(recommendations, n_fail),
            confidence_histogram=[
                Counter(label=label, count=count, share=count / n_fail if n_fail else 0.0)
                for label, count in sorted(confidence.items())
            ],
            daily=[
                DailyPoint(day=day, runs=runs, failures=fails)
                for day, (runs, fails) in sorted(daily.items())
            ],
            clusters=cluster_regressions(failures),
            heatmap={m: dict(cats) for m, cats in sorted(heatmap.items())},
        )


def cluster_regressions(failures: list[RegressionRecord]) -> list[FailureCluster]:
    """Group failing regressions into recurring problem areas.

    Two deterministic passes: exact signature groups first, then signature
    groups whose representative embeddings are close (cosine above the
    cluster threshold) merge via union-find. No randomness, no seeds; the
    same history always clusters the same way.
    """
    by_signature: dict[str, list[RegressionRecord]] = defaultdict(list)
    for record in failures:
        by_signature[record.signature.digest].append(record)

    digests = sorted(by_signature)
    parent = {d: d for d in digests}

    def find(d: str) -> str:
        while parent[d] != d:
            parent[d] = parent[parent[d]]
            d = parent[d]
        return d

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    representatives = {d: by_signature[d][-1].embedding for d in digests}
    for i, a in enumerate(digests):
        for b in digests[i + 1 :]:
            if cosine(representatives[a], representatives[b]) >= _CLUSTER_THRESHOLD:
                union(a, b)

    grouped: dict[str, list[str]] = defaultdict(list)
    for digest in digests:
        grouped[find(digest)].append(digest)

    clusters: list[FailureCluster] = []
    for root, members in grouped.items():
        records = [r for d in members for r in by_signature[d]]
        records.sort(key=lambda r: r.created_at, reverse=True)
        categories = TallyCounter(
            r.report.classification.category.display_name for r in records
        )
        modules = TallyCounter(m for r in records for m in r.signature.modules)
        dominant = categories.most_common(1)[0][0]
        top_module = modules.most_common(1)[0][0] if modules else None
        clusters.append(
            FailureCluster(
                cluster_id=f"cluster-{root.removeprefix('sig-')}",
                label=f"{dominant} in {top_module}" if top_module else dominant,
                size=len(records),
                category=dominant,
                modules=[m for m, _ in modules.most_common(5)],
                signatures=members,
                regression_ids=[r.regression_id for r in records],
                tests=sorted({r.test_name for r in records if r.test_name}),
            )
        )
    clusters.sort(key=lambda c: (-c.size, c.label))
    return clusters
