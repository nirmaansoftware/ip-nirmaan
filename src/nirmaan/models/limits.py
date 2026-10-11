"""How many times work may be tried again (M48): one object, one resolver.

Three limits count three different events, so they stay three numbers
(docs/UNIFIED_APPLICABILITY.md, section 2.4):

* ``attempts``: submissions the engine refuses in one review round (M26);
* ``review_rounds``: submissions independent review sends back (M27);
* ``retries``: failures the owner reports, after which ``on_failure`` says
  whether the task fails quietly or escalates.

A stage and a capability each declare a ``Limits``, any field left None. One
resolver takes each field from the first layer that sets it: the override
(the CLI), then the stage, then the capability, then ``DEFAULT_LIMITS``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OnFailure(str, Enum):
    RETRY_THEN_ESCALATE = "retry_then_escalate"
    ESCALATE = "escalate"
    FAIL = "fail"


class Limits(BaseModel):
    """A layer of limits: None leaves a field to the next layer."""

    model_config = ConfigDict(frozen=True)

    attempts: int | None = Field(default=None, ge=1, description="Refused submissions per review round (M26).")
    review_rounds: int | None = Field(default=None, ge=1, description="Submissions review may send back (M27).")
    retries: int | None = Field(default=None, ge=0, description="Reported failures that return the task to ready.")
    on_failure: OnFailure | None = Field(default=None, description="After the last retry: escalate, or just fail.")


DEFAULT_LIMITS = Limits(attempts=1, review_rounds=1, retries=1, on_failure=OnFailure.RETRY_THEN_ESCALATE)

#: The old field names, as data written before M48 used them, and the ``Limits`` field each became.
LEGACY_LIMIT_FIELDS = {"max_attempts": "attempts", "max_review_rounds": "review_rounds",
                       "max_retries": "retries", "on_failure": "on_failure"}


def resolve_limits(*layers: Limits | None) -> Limits:
    """Each field from the first layer that sets it, else the default: every field set."""
    chosen = {}
    for name in Limits.model_fields:
        values = [getattr(layer, name) for layer in layers if layer is not None]
        chosen[name] = next((v for v in values if v is not None), getattr(DEFAULT_LIMITS, name))
    return Limits(**chosen)


def migrate_limits(data):
    """Fold the old limit fields of a stage or capability (``max_retries`` and the rest) into ``limits``."""
    if not isinstance(data, dict) or not LEGACY_LIMIT_FIELDS.keys() & data.keys():
        return data
    data = dict(data)
    limits = data.get("limits") or {}
    limits = dict(limits) if isinstance(limits, dict) else limits.model_dump()
    for old, new in LEGACY_LIMIT_FIELDS.items():
        if old in data:
            value = data.pop(old)
            if value is not None:
                limits[new] = value
    data["limits"] = limits
    return data
