"""Requirement analysis: the declared vocabulary applied to a request.

Pure and deterministic. The analysis records which phrase produced each
conclusion, and anything it assumes (because the request was silent) is an
explicit, reviewable assumption with the question that would settle it.
"""

from __future__ import annotations

import hashlib
import re

from nirmaan.models import Assumption, Requirement, RequirementAnalysis
from nirmaan.org import Organization


def requirement_id(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return "req-" + hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]


def make_requirement(text: str, submitted_by: str = "owner") -> Requirement:
    return Requirement(id=requirement_id(text), text=text.strip(), submitted_by=submitted_by)


def analyze(org: Organization, requirement: Requirement) -> RequirementAnalysis:
    text = requirement.text

    # Intent: every rule that matches, lowest priority number wins.
    matched_intents: list[tuple[int, str, str]] = []
    for rule in org.intents:
        for pattern in rule.patterns:
            found = re.search(pattern, text, re.IGNORECASE)
            if found:
                matched_intents.append((rule.priority, rule.intent, found.group(0)))
                break
    matched_intents.sort()
    intent = matched_intents[0][1] if matched_intents else None
    intent_evidence = tuple(
        f"{i}: '{phrase}'" for _, i, phrase in matched_intents
    )

    # Features, with their implications closed transitively.
    evidence: dict[str, tuple[str, ...]] = {}
    for rule in org.features:
        hits = []
        for pattern in rule.patterns:
            hits += [m.group(0) for m in re.finditer(pattern, text, re.IGNORECASE)]
        if hits:
            evidence[rule.feature] = tuple(dict.fromkeys(hits))
    implied = {r.feature: r.implies for r in org.features}
    features = set(evidence)
    frontier = sorted(features)
    while frontier:
        source = frontier.pop()
        for extra in implied.get(source, ()):
            if extra not in features:
                features.add(extra)
                evidence.setdefault(extra, (f"implied by {source}",))
                frontier.append(extra)

    # Parameters: first match of the first matching pattern.
    parameters: dict[str, int] = {}
    for rule in org.parameters:
        for pattern in rule.patterns:
            found = re.search(pattern, text, re.IGNORECASE)
            if found:
                parameters[rule.name] = int(found.group(1))
                break

    # Assumptions: what we take as given because the request did not say.
    assumptions: list[Assumption] = []
    for rule in org.assumptions:
        if rule.applies_to_intents and intent not in rule.applies_to_intents:
            continue
        if not rule.when.holds(features):
            continue
        new = tuple(f for f in rule.assume_features if f not in features)
        assumptions.append(
            Assumption(id=rule.id, note=rule.note, question=rule.question, assumed_features=new)
        )
        features.update(new)

    return RequirementAnalysis(
        requirement_id=requirement.id,
        intent=intent,
        intent_evidence=intent_evidence,
        features=tuple(sorted(features)),
        feature_evidence={k: evidence.get(k, ("assumed",)) for k in sorted(features)},
        parameters=parameters,
        assumptions=tuple(assumptions),
        unrecognized=intent is None,
    )
