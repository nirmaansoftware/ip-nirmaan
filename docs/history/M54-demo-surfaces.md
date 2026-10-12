# Milestone 54 - Demo surfaces

Audit C of v1.24.0 found claims on the landing page that the engine does not
back, and CLI output that prints Python instead of words. Design:
`docs/DEMO_SURFACES.md`. Tests: `tests/test_nirmaan_demo_surfaces.py` and
`tests/test_ai_boundary.py::test_missing_credentials_raise_clean_error`,
written first and failing on main.

**The landing page (audit C H0, H2).** A blocked action changes nothing, so its
refusal is not in the audit trail; a refused AI attempt is. Gates wait for a
person's sign-off. The assurance ladder matches the engine: executed on
submission, verified when every required check is recorded, approved by an
authorized sign-off. The one live run is described as unrecorded, and the
reference blocks as proving the flow, not a model designing them unaided.

**The CLI (audit C H1, H4, M1).** `task escalate`, `status`, and `workflows`
print words, not reprs, JSON, or tuples. An unknown project is not a quoted
`KeyError`. `gaps` with nothing recorded says so. `veritriage analyze --ai`
without credentials warns in one line instead of a traceback.

**Docs (audit C H2, L11, L12).** The M26 blocks ran with scripted seat answers;
eighteen merged design docs no longer say they await review; the MCP doc lists
all 19 tools.
