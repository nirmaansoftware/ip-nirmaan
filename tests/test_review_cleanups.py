"""M47: small cleanups found by the principal-engineer review.

* One source for the model ID: the model profiles on the Nirmaan side, and a
  VeriTriage default kept equal to it by this test (VeriTriage may not import
  Nirmaan).
* ``max_chain_length``: its contract says what the engine does (0 is refused;
  omitting it means no limit), as ``docs/DFT_ADVANCED.md`` specifies.
* ``min_`` bounds are checked in one place, ``eda._within_limits``.
* No tracked doc cites a ``context.md`` section or entry that no longer exists.

See docs/history/M47-review-cleanups.md.
"""

from __future__ import annotations

import inspect
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# --- 1. One model ID ---------------------------------------------------------------------


def test_the_model_id_is_written_once_on_each_side():
    """The literal appears only in the profiles (Nirmaan) and in VeriTriage's own default."""
    out = subprocess.run(["git", "grep", "-l", "claude-opus-", "--", "src"], cwd=ROOT, capture_output=True,
                         text=True, check=False).stdout.split()
    assert sorted(out) == ["src/nirmaan/company/model_profiles.py", "src/veritriage/reasoning/ai.py"]


def test_veritriage_default_model_matches_the_profiles():
    from nirmaan.company.model_profiles import DEFAULT_MODEL, PROFILES
    from veritriage.cli.main import analyze
    from veritriage.reasoning import ai

    assert ai.DEFAULT_MODEL == DEFAULT_MODEL
    assert inspect.signature(ai.AIReasoner).parameters["model"].default == DEFAULT_MODEL
    assert inspect.signature(analyze).parameters["ai_model"].default.default == DEFAULT_MODEL
    assert any(p.model == DEFAULT_MODEL and p.provider == "anthropic" for p in PROFILES)


def test_both_claude_runtimes_use_the_profiles_model(monkeypatch):
    from nirmaan.company.model_profiles import DEFAULT_MODEL
    from nirmaan.integrations.veritriage import AnthropicProvider
    from nirmaan.runtime.claude_code import ClaudeCodeLLM

    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE_MODEL", raising=False)
    assert AnthropicProvider.model == DEFAULT_MODEL
    assert ClaudeCodeLLM(executable="claude").model == DEFAULT_MODEL


# --- 2. max_chain_length ------------------------------------------------------------------


def test_max_chain_length_contract_matches_the_engine(tmp_path):
    from nirmaan.company.tools import TOOLS
    from nirmaan.integrations.dft import _chain_params
    from nirmaan.integrations.eda import Job

    spec = next(t for t in TOOLS if t.id == "dft.scan_insert")
    text = next(p for p in spec.params if p.name == "max_chain_length").description
    assert "0 for no limit" not in text and "omit" in text.lower()

    def job(**params):
        return Job("dft.scan_insert", params, tmp_path, (), "top")

    assert _chain_params(job()) is None
    assert _chain_params(job(max_chain_length="4")) is None
    assert "positive integer" in _chain_params(job(max_chain_length="0"))


# --- 3. min_ bounds in one place ------------------------------------------------------------


def test_min_bounds_are_checked_only_by_the_runner():
    from nirmaan.integrations import dft, eda

    assert "min_" not in inspect.getsource(dft)
    assert "min_" in inspect.getsource(eda._within_limits)


# --- 4. No stale context.md references --------------------------------------------------------

_SECTION_REF = re.compile(r"context\.md`?\)?\s*(?:section\s+)?(\d+(?:\.\d+)*[a-z]?)\b")
_ENTRY_REF = re.compile(r"context\.md`?\s+M\d+\s+entry")


def test_no_doc_cites_a_context_md_section_that_is_gone():
    headings = set(re.findall(r"^#+\s+(\d+(?:\.\d+)*[a-z]?)\.?\s", (ROOT / "context.md").read_text(encoding="utf-8"),
                              re.M))
    files = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split()
    stale = []
    for name in files:
        if name.startswith("docs/history/"):
            continue  # history is verbatim, as it was written
        text = (ROOT / name).read_text(encoding="utf-8")
        stale += [f"{name}: context.md {m}" for m in _SECTION_REF.findall(text) if m not in headings]
        stale += [f"{name}: {m}" for m in _ENTRY_REF.findall(text)]
    assert not stale, stale
