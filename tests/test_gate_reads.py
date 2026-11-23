"""M85 (docs/GATE_INPUTS.md, section 2): a seat's setup reads no file of the host outside its run.

Must-fail: each way an SBY or eqy setup could name a file outside its folder (an absolute path, ``..``, ``~``, a
link out, a Yosys include folder or command file, ``hierarchy -libdir``, a ``$readmemh`` path) is refused before
any step runs, and the marker file's content appears in no output: not the summary, not the run's data, not any
file the run wrote, not what a seat in the loop reads. Two controls show the reads are live: with the check
bypassed, the content reaches the run's summary. Must-pass: an ordinary setup, and one that reads an approved file
linked beside it (M68), still prove.

The marker files are written in the test's own temporary directory only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from test_seat_tools import LoopSeat, _case, _run

from nirmaan.integrations import eda
from nirmaan.integrations.eda import backends_for, execute
from nirmaan.integrations.eda_guard import inside_problem, relative_problem, sby_problem, yosys_problem
from nirmaan.integrations.equivalence import setup_files
from nirmaan.runtime.seat_tools import screen

SBY = pytest.mark.skipif(shutil.which("sby") is None or shutil.which("yosys") is None, reason="needs sby")
#: What the marker file holds: a Verilog identifier, so a design that includes the file makes Yosys print it.
SECRET = "NIRMAAN_MARKER_4b1d"
#: A design that includes ``leak.vh`` where an expression goes: with ``default_nettype none``, Yosys names what is
#: in it in an error.
DESIGN = ('`default_nettype none\nmodule m(input wire clk, output wire y);\n  assign y = `include "leak.vh"\n'
          "  ;\nendmodule\n")


def backend(tool: str, name: str):
    return next(b for b in backends_for(tool) if b.name == name)


def host(tmp_path: Path) -> Path:
    """A folder outside the run with the marker in it, as ``leak.vh``, ``secret.txt`` and ``secret.v``."""
    folder = tmp_path / "host"
    folder.mkdir()
    for name in ("leak.vh", "secret.txt"):
        (folder / name).write_text(f"{SECRET}\n", encoding="utf-8")
    (folder / "secret.v").write_text(f"module {SECRET}; initial ${SECRET}; endmodule\n", encoding="utf-8")
    return folder


def setup(tmp_path: Path, script: str, files: str = "m.v", **extra: str) -> Path:
    run_in = tmp_path / "setup"
    run_in.mkdir(exist_ok=True)
    (run_in / "m.v").write_text(DESIGN, encoding="utf-8")
    for name, text in extra.items():
        (run_in / name).write_text(text, encoding="utf-8")
    sby = run_in / "f.sby"
    sby.write_text(f"[options]\nmode bmc\ndepth 2\n\n[engines]\nsmtbmc\n\n[script]\n{script}\n\n[files]\n{files}\n",
                   encoding="utf-8")
    return sby


def leaked_nowhere(outcome, tmp_path: Path) -> None:
    """The marker's content is in no output: the summary, the run's data, or any file outside the host folder."""
    assert SECRET not in outcome.summary, outcome.summary
    assert SECRET not in repr(outcome.data) and SECRET not in repr(outcome.metrics)
    for path in tmp_path.rglob("*"):
        if path.is_file() and not path.is_symlink() and "host" not in path.relative_to(tmp_path).parts:
            assert SECRET not in path.read_text(encoding="utf-8", errors="replace"), path


def refused(outcome, tmp_path: Path, *words: str) -> None:
    assert not outcome.succeeded and "refused, nothing ran" in outcome.summary, outcome.summary
    assert not outcome.references, "a refused run writes no log: no step ran"
    for word in words:
        assert word in outcome.summary, outcome.summary
    leaked_nowhere(outcome, tmp_path)


# --- Must-fail: SBY setups ------------------------------------------------------------------------------

#: Each way a setup could name a host file: (script, [files], what the refusal says). ``{host}`` is the folder.
READS = {
    "files-absolute": ("read -formal m.v\nprep -top m", "m.v\nleak.vh {host}/leak.vh", "not a relative file name"),
    "files-parent": ("read -formal m.v\nprep -top m", "m.v\nleak.vh ../host/leak.vh", "not a relative file name"),
    "files-home": ("read -formal m.v\nprep -top m", "m.v\nleak.vh ~/leak.vh", "not a relative file name"),
    "files-link": ("read -formal m.v\nprep -top m", "m.v\nleak.vh", "leads outside the run's own folder"),
    "files-dollar": ("read -formal m.v\nprep -top m", "m.v\n{host}/secret.v", "not a relative file name"),
    "script-absolute": ("read -formal m.v\nread -sv {host}/secret.v\nprep -top m", "m.v", "not a relative file"),
    "script-parent": ("read -formal m.v ../host/secret.v\nprep -top m", "m.v", "not a relative file name"),
    "script-share": ("read -formal m.v +/../x.v\nprep -top m", "m.v", "not a relative file name"),
    "script-glob": ("read -formal m.v *.v\nprep -top m", "m.v", "not a relative file name"),
    "include-glued": ("read -formal -I{host} m.v\nprep -top m", "m.v", "not a relative file name"),
    "include-apart": ("read -formal -I {host} m.v\nprep -top m", "m.v", "not a relative file name"),
    "include-incdir": ("read -incdir {host}\nread -formal m.v\nprep -top m", "m.v", "not a relative file name"),
    "include-defaults": ("verilog_defaults -add -I{host}\nread -formal m.v\nprep -top m", "m.v",
                         "not a relative file name"),
    "command-file": ("read -f cmds.f\nprep -top m", "m.v\ncmds.f", "a command file"),
    "libdir": ("read -formal m.v\nhierarchy -libdir {host} -top m\nprep -top m", "m.v", "not a relative file name"),
}


@pytest.mark.parametrize("tool,name", [("formal.run", "symbiyosys"), ("formal.cover", "symbiyosys-cover")])
@pytest.mark.parametrize("read", sorted(READS))
def test_a_setup_that_reads_a_host_file_is_refused_and_its_content_reaches_no_output(tmp_path, tool, name, read):
    folder = host(tmp_path)
    script, files, why = READS[read]
    sby = setup(tmp_path, script.format(host=folder), files.format(host=folder),
                **{"cmds.f": f"read_verilog -sv {folder}/secret.v\n"})
    if read == "files-link":
        (sby.parent / "leak.vh").symlink_to(folder / "leak.vh")
    outcome = execute(backend(tool, name), {"sby": str(sby), "workdir": str(tmp_path / "run")})
    refused(outcome, tmp_path, why)


@SBY
@pytest.mark.parametrize("read", ["files-absolute", "include-glued"])
def test_control_without_the_check_the_host_file_reaches_the_summary(tmp_path, monkeypatch, read):
    """The reads above are live: with the check bypassed, what the host file holds is in the run's summary."""
    folder = host(tmp_path)
    script, files, _ = READS[read]
    sby = setup(tmp_path, script.format(host=folder), files.format(host=folder))
    monkeypatch.setattr(eda, "sby_problem", lambda *a: None)
    outcome = execute(backend("formal.run", "symbiyosys"), {"sby": str(sby), "workdir": str(tmp_path / "run")})
    assert SECRET in outcome.summary, outcome.summary


# --- Gate ET17: a [files] entry is the run's own, whatever the screen allowed ---------------------------------
#
# council/records/2026-11-22-eda-tools-seat-account.md, third addendum, decision E3: a file a setup's [files] names is
# an input of the run (what the seat account's view holds), and is read by the caller for ``formal.cover``, only when
# it is the run's own: inside the setup's folder, or a file the harness gave the run. Each test bypasses the screen.


def test_a_files_entry_outside_the_run_is_no_input_of_it(tmp_path, monkeypatch):
    """``eda.seat_inputs`` names an entry by an absolute name, a parent name or a link out of the folder as no input;
    the setup's own file and the approved file linked beside it (M68), which the run is given, stay inputs."""
    folder = host(tmp_path)
    approved = tmp_path / "approved" / "a.v"
    approved.parent.mkdir()
    approved.write_text("module a; endmodule\n", encoding="utf-8")
    sby = setup(tmp_path, "read -formal m.v\nprep -top m",
                f"m.v\nleak.vh {folder}/leak.vh\nup.txt ../host/secret.txt\nout.v\na.v\n{folder}/secret.v")
    (sby.parent / "out.v").symlink_to(folder / "secret.v")
    (sby.parent / "a.v").symlink_to(approved)
    monkeypatch.setattr(eda, "sby_problem", lambda *a: None)
    job = eda.Job("formal.run", {"sby": str(sby), "sources": str(approved)}, tmp_path / "run",
                  (str(approved.resolve()),), None)
    inputs = eda.seat_inputs(backend("formal.run", "symbiyosys"), job)
    assert inputs == [str(approved.resolve()), str(sby.resolve()), str((sby.parent / "m.v").resolve())], inputs
    assert not any(Path(p).is_relative_to(folder.resolve()) for p in inputs)


def test_the_cover_run_reads_and_copies_no_files_entry_outside_the_run(tmp_path, monkeypatch):
    """``formal.cover`` reads each Verilog file of the setup as the caller and writes a copy with derived covers into
    the run's directory (M29); an entry outside the run is neither read nor copied, and the cover setup names it as
    the seat's setup does, a file SBY itself must open."""
    folder = host(tmp_path)
    sby = setup(tmp_path, "read -formal m.v\nprep -top m", f"m.v\nleak.vh {folder}/leak.vh\nout.v\n{folder}/secret.v")
    (sby.parent / "out.v").symlink_to(folder / "secret.v")
    monkeypatch.setattr(eda, "sby_problem", lambda *a: None)
    reads, read_text = [], Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: reads.append(self.resolve()) or read_text(self, *a, **k))
    run = tmp_path / "run"
    run.mkdir()
    job = eda.Job("formal.cover", {"sby": str(sby)}, run, (), None)
    assert eda._sby_cover_check(job) is None
    [[*_, cover]] = eda._sby_cover(job)
    assert not [p for p in reads if p.is_relative_to(folder.resolve())], reads
    assert sorted(p.name for p in (run / "antecedents").iterdir()) == ["m.v"]
    lines = read_text(Path(cover)).splitlines()
    assert f"leak.vh {(folder / 'leak.vh').resolve()}" in lines and str((folder / "secret.v").resolve()) in lines
    for path in run.rglob("*"):
        assert SECRET not in read_text(path, encoding="utf-8", errors="replace"), path


@SBY
@pytest.mark.parametrize("read", ["files-absolute"])
def test_control_without_the_check_the_host_file_reaches_the_cover_summary(tmp_path, monkeypatch, read):
    """The control above through ``formal.cover``: with the check bypassed, the read is live as the caller, and the
    host file's content is in the cover run's summary. As the seat account the entry is no input of the run and is
    not read for the cover (gate ET17), so SBY itself must open it, and the account's view does not hold it."""
    folder = host(tmp_path)
    script, files, _ = READS[read]
    sby = setup(tmp_path, script.format(host=folder), files.format(host=folder))
    monkeypatch.setattr(eda, "sby_problem", lambda *a: None)
    outcome = execute(backend("formal.cover", "symbiyosys-cover"), {"sby": str(sby), "workdir": str(tmp_path / "run")})
    assert SECRET in outcome.summary, outcome.summary


def test_no_file_gate_et17_changes_is_harness_code():
    """Gate ET7 for gate ET17: the repair is in the gate backends, none of them harness code, so no fingerprint moves."""
    from nirmaan.runtime import harness

    changed = {"nirmaan/integrations/eda.py"}
    assert not changed & {*harness.CODE, *harness.LOOP_CODE, *harness.FLOW_CODE}


def test_a_refusal_never_quotes_the_host_file(tmp_path):
    """Before M85 the Verilog check read a [files] source wherever it was, and named the ``$`` words it found."""
    folder = host(tmp_path)
    problem = sby_problem(setup(tmp_path, "read -formal m.v\nprep -top m", f"m.v\n{folder}/secret.v"))
    assert problem and SECRET not in problem


# --- Must-fail: in the loop, behind the screen ---------------------------------------------------------


@SBY
def test_a_seat_in_the_loop_never_reads_a_host_file(nirmaan_org, fixed_clock, tmp_path):
    """The M75 screen lets ``-I/<folder>`` through (a word that starts with ``-``); the gate's check refuses it."""
    folder = host(tmp_path)
    proof = (f"[options]\nmode bmc\ndepth 2\n\n[engines]\nsmtbmc\n\n[script]\nread -formal -I{folder} m.v\n"
             "prep -top m\n\n[files]\nm.v\n")
    files = [{"path": "m.v", "kind": "rtl_source", "content": DESIGN, "entry": "m"},
             {"path": "f.sby", "kind": "formal_spec", "content": proof}]
    assert all(screen(f["path"], f["content"]) is None for f in files)
    seat = LoopSeat(_case(), calls=[("formal_run", {"files": files})])
    result, _ = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    [(text, error)] = seat.results
    assert error and "refused, nothing ran" in text and SECRET not in text, text
    assert SECRET not in repr(result)
    for path in (tmp_path / "box").rglob("*"):
        if path.is_file():
            assert SECRET not in path.read_text(encoding="utf-8", errors="replace"), path


# --- Must-fail: eqy setups ----------------------------------------------------------------------------


def eqy(tmp_path: Path, gold: str) -> Path:
    run_in = tmp_path / "setup"
    run_in.mkdir(exist_ok=True)
    (run_in / "n.v").write_text("module m(input a, output b); assign b = a; endmodule\n", encoding="utf-8")
    path = run_in / "s.eqy"
    path.write_text(f"[gold]\n{gold}\nprep -top m\n\n[gate]\nread_verilog -sv n.v\nprep -top m\n\n"
                    "[strategy sby]\nuse sby\nengine smtbmc\ndepth 10\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("gold", ["read_verilog -sv -I{host} n.v", "read_verilog -sv -I {host} n.v",
                                  "read -incdir {host}\nread_verilog -sv n.v", "read_verilog -sv {host}/secret.v",
                                  "read -f cmds.f", "read_verilog -sv n.v\nhierarchy -libdir {host}"])
def test_an_equivalence_setup_that_names_a_host_folder_is_refused(tmp_path, gold):
    folder = host(tmp_path)
    sides, problem = setup_files(eqy(tmp_path, gold.format(host=folder)))
    assert not sides and problem and "refused, nothing ran" in problem and SECRET not in problem


@pytest.mark.parametrize("how", ["link", "readmem"])
def test_an_equivalence_setup_that_reads_a_host_file_another_way_is_refused(tmp_path, how):
    folder = host(tmp_path)
    setup_path = eqy(tmp_path, "read_verilog -sv g.v")
    if how == "link":
        (setup_path.parent / "g.v").symlink_to(folder / "secret.v")
    else:  # Yosys reads a $readmemh file as it elaborates
        (setup_path.parent / "g.v").write_text(
            f'module m(input a, output b); reg [7:0] r [0:1]; initial $readmemh("{folder}/leak.vh", r);\n'
            "assign b = a; endmodule\n", encoding="utf-8")
    outcome = execute(backend("equivalence.run", "eqy"), {"eqy": str(setup_path), "workdir": str(tmp_path / "run")})
    refused(outcome, tmp_path, "leads outside the run's own folder" if how == "link" else "$readmemh")


# --- Must-pass ----------------------------------------------------------------------------------------


@SBY
def test_an_ordinary_setup_still_proves(tmp_path):
    sby = setup(tmp_path, "read -formal m.v\nprep -top m", "m.v")
    (sby.parent / "m.v").write_text("module m(input wire a, output wire b); assign b = a; endmodule\n")
    outcome = execute(backend("formal.run", "symbiyosys"), {"sby": str(sby)})
    assert outcome.succeeded, outcome.summary


@SBY
def test_a_setup_over_an_approved_file_linked_beside_it_still_proves(tmp_path):
    """M68's ``beside``: the platform links an approved file beside the setup and gives it as ``sources``."""
    approved = tmp_path / "approved" / "m.v"
    approved.parent.mkdir()
    approved.write_text("module m(input wire a, output wire b); assign b = a; endmodule\n", encoding="utf-8")
    sby = setup(tmp_path, "read -formal m.v\nprep -top m", "m.v")
    (sby.parent / "m.v").unlink()
    (sby.parent / "m.v").symlink_to(approved)
    outcome = execute(backend("formal.run", "symbiyosys"), {"sby": str(sby), "sources": str(approved)})
    assert outcome.succeeded, outcome.summary
    # The same link, with the run not given that file, is a link out of the folder.
    assert "leads outside" in execute(backend("formal.run", "symbiyosys"), {"sby": str(sby)}).summary


@pytest.mark.parametrize("line", ["read -formal m.v", "read -formal -DWIDTH=8 -D DEPTH=4 m.v sub/n.sv",
                                  "read -define WIDTH=8 NAME=/x", "read_verilog -sv -Iinc -I inc2 m.v",
                                  "read -incdir inc", "verilog_defaults -add -Iinc", "read_verilog -setattr keep m.v",
                                  "hierarchy -check -top m", "hierarchy -libdir lib -top m", "chparam -set W 4 m",
                                  "prep -top m"])
def test_ordinary_yosys_reads_pass(line):
    assert yosys_problem([line], "s") is None


def test_names_and_links(tmp_path):
    for name in ("m.v", "rtl/m.v", "a_b-c.sv"):
        assert relative_problem(name, "s") is None
    for name in ("/etc/hosts", "../m.v", "a/../../m.v", "~/m.v", "+/m.v", "*.v", '"m.v"', "", "-x"):
        assert relative_problem(name, "s"), name
    inside = tmp_path / "in"
    inside.mkdir()
    (inside / "m.v").write_text("x")
    (inside / "out.v").symlink_to(tmp_path / "elsewhere.v")
    assert inside_problem(inside / "m.v", inside, (), "s", "m.v") is None
    assert inside_problem(inside / "out.v", inside, (), "s", "out.v")
    assert inside_problem(inside / "out.v", inside, [str(tmp_path / "elsewhere.v")], "s", "out.v") is None
    assert str(tmp_path / "elsewhere.v") not in inside_problem(inside / "out.v", inside, (), "s", "out.v")


# --- Must-fail: an include that leads out of the run (ip#309's follow-up) ------------------------------

#: What the host header holds: a ``$`` word, which the Verilog check names in a refusal when it reads the file.
WORD = f"${SECRET}"
#: A design that includes ``leak.vh`` (or ``inc/leak.vh``), which is not a ``[files]`` entry.
INCLUDES = 'module m(input wire a, output wire b); assign b = a;\n  `include "{name}"\nendmodule\n'


def linked_include(tmp_path: Path, how: str) -> Path:
    """A setup folder whose ``m.v`` includes a host file through a link: the file itself, or a folder."""
    folder = tmp_path / "host"
    folder.mkdir()
    (folder / "leak.vh").write_text(f"initial {WORD};\n", encoding="utf-8")
    sby = setup(tmp_path, "read -formal m.v\nprep -top m", "m.v")
    (sby.parent / "m.v").write_text(INCLUDES.format(name="leak.vh" if how == "file" else "inc/leak.vh"))
    if how == "file":
        (sby.parent / "leak.vh").symlink_to(folder / "leak.vh")
    else:
        (sby.parent / "inc").symlink_to(folder)
    return sby


def seat_texts(outcome) -> tuple[str, str]:
    """What a seat reads of a failed run: the attempts-3 repair text (M74) and the in-loop broker's report (M75)."""
    from types import SimpleNamespace

    from nirmaan.runtime.context import AttemptView, FailedRun
    from nirmaan.runtime.files import excerpt
    from nirmaan.runtime.prompt import ToolNote, _repair
    from nirmaan.runtime.seat_tools import SeatTools

    log = outcome.references[0] if outcome.references else None
    found, note = excerpt(log)
    failed = FailedRun(run="run-1", tool="formal.run", summary=outcome.summary, log=log, evidence=None,
                       excerpt=tuple(found), excerpt_note=note)
    attempt = AttemptView(id="a-1", number=1, refusal=f"formal.run failed: {outcome.summary}", reviews=(),
                          failed_runs=(failed,), artifacts=())
    repair = "\n".join(_repair((attempt,), (), {"run-1": "[run:1]"}))
    broker = SimpleNamespace(calls=[], remaining=lambda: 60,
                             _handle=SimpleNamespace(recorded=lambda run: SimpleNamespace(references=outcome.references)))
    report = SeatTools._report(broker, (ToolNote("formal.run", "run-1", outcome.succeeded, outcome.summary),))
    return repair, report


@pytest.mark.parametrize("how", ["file", "folder"])
@pytest.mark.parametrize("tool,name", [("formal.run", "symbiyosys"), ("formal.cover", "symbiyosys-cover"),
                                       ("simulator.run", "icarus"), ("lint.run", "verilator-lint")])
def test_an_include_linked_out_of_the_run_is_refused_unread_and_quoted_nowhere(tmp_path, how, tool, name):
    sby = linked_include(tmp_path, how)
    params = ({"sby": str(sby)} if tool.startswith("formal.") else {"sources": str(sby.parent / "m.v"), "top": "m"})
    outcome = execute(backend(tool, name), {**params, "workdir": str(tmp_path / "run")})
    refused(outcome, tmp_path, "includes", "leads outside the sandbox")
    assert "leak.vh" in outcome.summary and str(tmp_path / "host") not in outcome.summary, outcome.summary
    for text in seat_texts(outcome):
        assert SECRET not in text and "leads outside the sandbox" in text, text


@pytest.mark.parametrize("how", ["file", "folder"])
def test_an_equivalence_include_linked_out_of_the_run_is_refused_unread_and_quoted_nowhere(tmp_path, how):
    folder = tmp_path / "host"
    folder.mkdir()
    (folder / "leak.vh").write_text(f"initial {WORD};\n", encoding="utf-8")
    setup_path = eqy(tmp_path, "read_verilog -sv g.v")
    (setup_path.parent / "g.v").write_text(INCLUDES.format(name="leak.vh" if how == "file" else "inc/leak.vh"),
                                           encoding="utf-8")
    if how == "file":
        (setup_path.parent / "leak.vh").symlink_to(folder / "leak.vh")
    else:
        (setup_path.parent / "inc").symlink_to(folder)
    outcome = execute(backend("equivalence.run", "eqy"), {"eqy": str(setup_path), "workdir": str(tmp_path / "run")})
    refused(outcome, tmp_path, "includes", "leads outside the sandbox")
    assert "leak.vh" in outcome.summary and str(folder) not in outcome.summary, outcome.summary
    for text in seat_texts(outcome):
        assert SECRET not in text and "leads outside the sandbox" in text, text


def test_control_an_include_inside_the_run_is_read_and_named(tmp_path):
    """The check reads includes: the same header inside the setup's folder is read, and the refusal says why."""
    sby = linked_include(tmp_path, "file")
    (sby.parent / "leak.vh").unlink()
    (sby.parent / "leak.vh").write_text('initial $fopen("x");\n', encoding="utf-8")
    problem = sby_problem(sby)
    assert problem and "leak.vh uses $fopen" in problem and "outside the sandbox" not in problem
    outcome = execute(backend("formal.run", "symbiyosys"), {"sby": str(sby), "workdir": str(tmp_path / "run")})
    for text in seat_texts(outcome):
        assert "leak.vh uses $fopen" in text, text


def test_includes_inside_the_run_still_pass(tmp_path):
    """Must-pass: an include beside the file, in a folder of it, and beside an approved file given to the run."""
    sby = linked_include(tmp_path, "file")
    (sby.parent / "leak.vh").unlink()
    (sby.parent / "leak.vh").write_text("// a header\n", encoding="utf-8")
    assert sby_problem(sby) is None
    (sby.parent / "sub").mkdir()
    (sby.parent / "sub" / "leak.vh").write_text("// a header\n", encoding="utf-8")
    (sby.parent / "m.v").write_text(INCLUDES.format(name="sub/leak.vh"))
    assert sby_problem(sby) is None
    approved = tmp_path / "approved"
    approved.mkdir()
    (approved / "m.v").write_text(INCLUDES.format(name="h.vh"), encoding="utf-8")
    (approved / "h.vh").write_text("// a header\n", encoding="utf-8")
    (sby.parent / "m.v").unlink()
    (sby.parent / "m.v").symlink_to(approved / "m.v")
    assert sby_problem(sby, [str(approved / "m.v")]) is None


def test_no_file_this_milestone_changes_is_harness_code():
    """docs/GATE_INPUTS.md, section 5: the gate files are not in the harness fingerprint, so it is unchanged."""
    from nirmaan.runtime import harness

    changed = {"nirmaan/integrations/eda_guard.py", "nirmaan/integrations/eda.py",
               "nirmaan/integrations/equivalence.py"}
    assert not changed & set(harness.CODE) and not changed & set(harness.LOOP_CODE)
