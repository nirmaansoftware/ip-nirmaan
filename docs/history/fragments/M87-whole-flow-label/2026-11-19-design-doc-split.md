**The design document split (follow-up).** `docs/WHOLE_FLOW.md` became an
index of its parts, each now its own file in `docs/whole_flow/`
(`01-label-and-list.md` to `12-not-yet.md`, text unchanged), because the G3
pull requests kept conflicting in the one file. Gate status is one file per
gate (`docs/whole_flow/gates/WF<NN>.md`; WF1 is the only one recorded so far).
A pull request now edits only the parts it changes, and a new part is a new
numbered file and one index line. `tests/test_status_docs.py` holds the index
and the names. This is the first entry written as a history fragment.
