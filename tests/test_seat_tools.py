"""Tools in the loop (M75): the seat calls brokered checks during its attempt, under decision 4's conditions.

Council record 2026-11-14 (pilot retrospective), decision 4, and gate RT5: tools in the loop merges only with
every condition shown by a test. Each section below is one condition. The seat is a mock (``LoopSeat``) or a
fake ``claude`` executable that speaks MCP to the real relay; no test calls a model.
"""

from __future__ import annotations

import json
import shutil
import stat
import sys
import time
from pathlib import Path

import pytest

from laws import needs

from nirmaan.evals import EvalError, evaluate, load_cases, load_record, record_trial, replay_llm
from nirmaan.models import EvidenceKind, SeatToolCall
from nirmaan.runtime import ModelRuntime, harness
from nirmaan.runtime.claude_code import ClaudeCodeLLM
from nirmaan.runtime.harness import fingerprint, harness_sha256
from nirmaan.runtime.seat_tools import RELAY, loop_command, screen
from nirmaan.work.policy import satisfies

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIFO = ROOT / "tests" / "fixtures" / "rtl" / "sync_fifo"
VARIANT = "tools-in-loop"
EDA = needs("verilator", "iverilog", "vvp", "yosys", "sby")


def _case(case_id: str = "rtl/sync-fifo"):
    return next(c for c in load_cases(ROOT / "evals") if c.id == case_id)


def _rtl(text: str | None = None, path: str = "sync_fifo.v") -> dict:
    return {"path": path, "kind": "rtl_source", "content": (FIFO / "sync_fifo.v").read_text() if text is None
            else text, "entry": "sync_fifo"}


class LoopSeat:
    """A mock seat that can call brokered tools: it makes the scripted calls, then gives its answer.

    The answer is the case's reference (``replay_llm``), unless ``answer`` rewrites it from the call results.
    """

    name = "loop-seat"
    takes_seat_tools = True

    def __init__(self, case, calls=(), answer=None) -> None:
        self._inner = replay_llm(case, ROOT)
        self._calls, self._answer = list(calls), answer
        self.results: list[tuple[str, bool]] = []
        self.prompts: list = []
        self.sessions: list = []

    def complete(self, prompt, tools=None):
        self.prompts.append(prompt)
        if tools is not None:
            self.sessions.append(tools)
            self.results += [tools.call(name, args) for name, args in self._calls]
        completion = self._inner.complete(prompt)
        return self._answer(completion, self.results) if self._answer else completion


def _run(nirmaan_org, fixed_clock, tmp_path, seat, case=None, variant=VARIANT):
    runtime = ModelRuntime(seat, runtime_id="loop-seat")
    return evaluate(nirmaan_org, case or _case(), runtime, replay=False, repo=ROOT, sandbox=tmp_path / "box",
                    clock=fixed_clock, variant=variant)


# --- A named variant, with its server code and tool pins in its fingerprint -------------------------


def test_tools_in_the_loop_is_a_named_variant_beside_the_default_and_attempts_3():
    assert harness.VARIANTS == {"default": {}, "attempts-3": {"attempts": 3}, VARIANT: {"tools": True}}
    assert len({harness_sha256(), harness_sha256(variant="attempts-3"), harness_sha256(variant=VARIANT)}) == 3
    loop = fingerprint(variant=VARIANT)["loop"]
    assert set(loop["settings"]) == set(harness.LOOP_SETTINGS)
    assert set(loop["code"]) == set(harness.LOOP_CODE) and all(d.startswith("sha256:") for d in loop["code"].values())
    assert loop["tools"] == list(harness.loop_tools()) == ["lint.run", "simulator.run", "formal.run",
                                                           "formal.cover"]
    assert set(loop["pins"]) == set(harness.loop_tools())
    assert "loop" not in fingerprint() and "loop" not in fingerprint(variant="attempts-3")


def test_the_server_code_changes_the_variants_fingerprint_and_never_the_defaults(monkeypatch, tmp_path):
    default, before = harness_sha256(), harness_sha256(variant=VARIANT)
    for rel in (*harness.CODE, *harness.LOOP_CODE):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / rel, tmp_path / rel)
    monkeypatch.setattr(harness, "SOURCE_ROOT", tmp_path)
    assert harness_sha256(variant=VARIANT) == before
    for rel in harness.LOOP_CODE:
        original = (tmp_path / rel).read_bytes()
        (tmp_path / rel).write_bytes(original + b"# an edit\n")
        assert harness_sha256(variant=VARIANT) != before and harness_sha256() == default, rel
        (tmp_path / rel).write_bytes(original)


@pytest.mark.parametrize("name", harness.LOOP_SETTINGS)
def test_each_loop_setting_changes_the_variants_fingerprint_and_never_the_defaults(monkeypatch, name):
    default, before = harness_sha256(), harness_sha256(variant=VARIANT)
    value = getattr(harness, name)
    monkeypatch.setattr(harness, name, value + 1 if isinstance(value, int) else
                        (*value, "changed") if isinstance(value, tuple) else value + " changed")
    assert harness_sha256(variant=VARIANT) != before and harness_sha256() == default


def test_the_loop_tools_are_company_data_in_the_variants_fingerprint_only(monkeypatch):
    from nirmaan.company import tools

    default, before = harness_sha256(), harness_sha256(variant=VARIANT)
    monkeypatch.setattr(tools, "IN_LOOP", ("lint.run",))
    assert harness_sha256(variant=VARIANT) != before and harness_sha256() == default


def test_the_tool_pins_are_in_the_variants_fingerprint(monkeypatch):
    before = harness_sha256(variant=VARIANT)
    pins = harness.tool_pins()
    assert all(isinstance(v, str) and v for found in pins.values() for v in found.values())
    monkeypatch.setattr(harness, "tool_pins", lambda: {**pins, "lint.run": {"verilator": "Verilator 0.0"}})
    assert harness_sha256(variant=VARIANT) != before


# --- Brokered tools only, under the seat's role: no shell, file or network tool ----------------------


def test_the_seat_is_offered_only_the_loop_tools_its_task_runs_over_its_files(nirmaan_org, fixed_clock, tmp_path):
    seat = LoopSeat(_case())
    _run(nirmaan_org, fixed_clock, tmp_path, seat)
    [session] = seat.sessions
    # The seat's task also runs synth.run over its files, and its role is granted it: not a loop tool, not offered.
    assert session.names() == ("lint_run", "simulator_run", "formal_run", "formal_cover")
    assert [t["name"] for t in session.listing()] == list(session.names())
    assert "synth_run" not in session.names()
    assert seat.prompts[0].system.endswith(session.system_note()) and "no shell" in session.system_note()


@pytest.mark.parametrize("name", ["Bash", "Read", "Write", "WebFetch", "synth_run", "status_read", "lint.run",
                                  "mcp__nirmaan-broker__lint_run", 7, None])
def test_a_call_outside_the_allowlist_is_refused_recorded_and_runs_nothing(nirmaan_org, fixed_clock, tmp_path, name):
    seat = LoopSeat(_case(), calls=[(name, {"files": [_rtl()]})])
    result, engine = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    [(text, error)] = seat.results
    assert error and text.startswith("Refused, nothing ran:") and "is not a brokered tool of this seat" in text
    [call] = result.tool_calls
    assert call.refused and call.runs == () and call.succeeded is None
    assert not any(run.advisory for run in engine.state.tool_runs.values())  # nothing ran for it


def test_the_variant_needs_a_seat_whose_model_can_call_tools(nirmaan_org, fixed_clock, tmp_path):
    from nirmaan.runtime import MockLLM

    with pytest.raises(EvalError, match="seats a model that can call brokered tools"):
        evaluate(nirmaan_org, _case(), ModelRuntime(MockLLM(), runtime_id="mock-llm"), replay=False, repo=ROOT,
                 sandbox=tmp_path / "box", clock=fixed_clock, variant=VARIANT)


def test_the_default_harness_gives_the_seat_no_tools(nirmaan_org, fixed_clock, tmp_path):
    seat = LoopSeat(_case(), calls=[("lint_run", {"files": [_rtl()]})])
    result, _ = _run(nirmaan_org, fixed_clock, tmp_path, seat, variant="default")
    assert seat.sessions == [] and seat.results == [] and result.tool_calls == ()
    assert harness.LOOP_SYSTEM.splitlines()[0] not in seat.prompts[0].system


# --- Paths limited to the seat's workspace, so held-out files are unreachable ---------------------------


HELD_OUT = str(FIFO / "sync_fifo_depth5.sby")


@pytest.mark.parametrize("item, why", [
    ({**_rtl(), "path": "/etc/passwd.v"}, "unsafe file path"),
    ({**_rtl(), "path": "../up.v"}, "unsafe file path"),
    ({**_rtl(), "path": "tb.py"}, "files only"),
    ({**_rtl(), "path": "image.hex"}, "files only"),
    ({**_rtl(), "kind": "netlist"}, "is not one this tool takes"),
    ({**_rtl(), "entry": "top; rm -rf"}, "entry must be a module name"),
    ({**_rtl(), "extra": 1}, "nothing else"),
    (_rtl(f'`include "{HELD_OUT}"\nmodule sync_fifo; endmodule\n'), "only a relative file of the call"),
    (_rtl('`include "../../tests/x.v"\nmodule sync_fifo; endmodule\n'), "only a relative file of the call"),
    (_rtl('`define P "x"\n`include `P\nmodule sync_fifo; endmodule\n'), "only a relative file of the call"),
    (_rtl(f'module sync_fifo; initial $readmemh("{HELD_OUT}", m); endmodule\n'), "$readmemh"),
    (_rtl('module sync_fifo; integer f; initial f = $fopen("out.txt", "w"); endmodule\n'), "$fopen"),
    (_rtl('module sync_fifo; initial $system("curl http://example.com"); endmodule\n'), "$system"),
    (_rtl('module sync_fifo; initial $c("system(\\"id\\");"); endmodule\n'), "$c"),
    (_rtl('import "DPI-C" function int getpid();\nmodule sync_fifo; endmodule\n'), "DPI"),
    (_rtl('module sync_fifo; initial $display("/etc/passwd"); endmodule\n'), "names a path outside the call"),
    (_rtl('module sync_fifo; initial $display("~/x"); endmodule\n'), "names a path outside the call"),
    (_rtl('module sync_fifo; initial $display("\\057etc"); endmodule\n'), "names a path outside the call"),
])
def test_a_file_that_could_reach_outside_the_call_is_refused_before_anything_runs(
        nirmaan_org, fixed_clock, tmp_path, item, why):
    seat = LoopSeat(_case(), calls=[("lint_run", {"files": [item]})])
    result, engine = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    [(text, error)] = seat.results
    assert error and text.startswith("Refused, nothing ran:") and why in text, text
    assert result.tool_calls[0].refused and not any(r.advisory for r in engine.state.tool_runs.values())
    assert not list((tmp_path / "box" / "seat").rglob("*.loop/*/*"))  # nothing was written for it


SBY = (FIFO / "sync_fifo.sby").read_text()


@pytest.mark.parametrize("text, why", [
    (SBY.replace("[script]\n", "[script]\n!cat /etc/passwd\n"), "names a path outside"),
    (SBY.replace("[script]\n", "[script]\n!id\n"), "runs a shell command"),
    (SBY.replace("[script]\n", "[script]\nexec -- id\n"), "runs 'exec'"),
    (SBY.replace("[script]\n", "[script]\ntee -o out.txt stat\n"), "runs 'tee'"),
    (SBY.replace("[script]\n", "[script]\nprep; script other.ys\n"), "runs 'script'"),
    (SBY.replace("[files]\n", f"[files]\n{HELD_OUT}\n"), "names a path outside"),
    (SBY.replace("[files]\n", "[files]\n../../x.v\n"), "names a path outside"),
    (SBY.replace("[engines]\n", "[engines]\nsmtbmc yices -- --dumpsmt2 x\n"), "runs the engine"),
    (SBY.replace("[engines]\n", "[engines]\naiger suprove\n"), "runs the engine"),
    (SBY + "\n[setup]\nx\n", "has a [setup] section"),
    (SBY + '\n[file inc.v]\nmodule m; initial $system("id"); endmodule\n', "$system"),
])
def test_a_proof_setup_that_could_run_a_command_or_read_outside_the_call_is_refused(text, why):
    problem = screen("sync_fifo.sby", text)
    assert problem and why in problem, problem


def test_the_screen_passes_every_reference_file_of_the_rtl_cases():
    # The screen refuses what could leave the call, not ordinary RTL, testbenches or proof setups.
    for case in load_cases(ROOT / "evals"):
        for ref in case.reference:
            path = Path(ref.path)
            if path.suffix in harness.LOOP_SUFFIXES:
                assert screen(path.name, (ROOT / path).read_text()) is None, ref.path


@EDA
def test_every_file_and_run_of_a_call_is_inside_the_seats_workspace(nirmaan_org, fixed_clock, tmp_path):
    seat = LoopSeat(_case(), calls=[("lint_run", {"files": [_rtl()]})])
    result, engine = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    workspace = (tmp_path / "box" / "seat").resolve()
    [run] = [r for r in engine.state.tool_runs.values() if r.advisory]
    assert Path(str(run.params["workdir"])).resolve().is_relative_to(workspace)
    assert all(Path(p).resolve().is_relative_to(workspace) for p in run.params["sources"])
    assert all(Path(ref).resolve().is_relative_to(workspace) for ref in run.references)


# --- No credential in a tool run's environment -------------------------------------------------------------


@EDA
def test_no_credential_reaches_a_brokered_run(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    from nirmaan.integrations import eda

    for key in ("ANTHROPIC_API_KEY", "GH_TOKEN", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "NIRMAAN_LIVE_TOKEN"):
        monkeypatch.setenv(key, f"secret-{key.lower()}-1234567890")
    seen: list[dict] = []
    real = eda._run_step

    def spy(argv, cwd, env, deadline):
        seen.append(dict(env))
        return real(argv, cwd, env, deadline)

    monkeypatch.setattr(eda, "_run_step", spy)
    seat = LoopSeat(_case(), calls=[("lint_run", {"files": [_rtl()]})])
    _run(nirmaan_org, fixed_clock, tmp_path, seat)
    assert seen and seat.results[0][0].count("[run:") == 1
    for env in seen:
        assert not any(value.startswith("secret-") for value in env.values()), sorted(env)


def test_the_relay_starts_with_an_empty_environment_in_isolated_mode(nirmaan_org, fixed_clock, tmp_path):
    from nirmaan.runtime.seat_tools import Endpoint

    seat = LoopSeat(_case())
    _run(nirmaan_org, fixed_clock, tmp_path, seat)
    with Endpoint(seat.sessions[0]) as endpoint:
        config = json.loads(endpoint.config.read_text())
        assert list(config["mcpServers"]) == [harness.LOOP_SERVER]  # one server: this one
        server = config["mcpServers"][harness.LOOP_SERVER]
        assert server["command"] == "/usr/bin/env" and server["args"][:3] == ["-i", sys.executable, "-I"]
        assert server["args"][3] == str(RELAY) and server["env"] == {}
        assert stat.S_IMODE(endpoint.dir.stat().st_mode) == 0o700
        assert stat.S_IMODE((endpoint.dir / "token").stat().st_mode) == 0o600
        # A request without this attempt's token is refused, and runs and records nothing.
        assert endpoint.handle(json.dumps({"token": "wrong", "method": "tools/call", "params": {
            "name": "lint_run", "arguments": {"files": [_rtl()]}}}).encode())["error"].startswith("refused")
        assert len(seat.sessions[0].calls) == 0
    assert not endpoint.dir.exists()
    relay = RELAY.read_text()
    assert "import nirmaan" not in relay and "from nirmaan" not in relay and "subprocess" not in relay


# --- A cap on calls and time per attempt, a timeout being a failed attempt -------------------------------


def test_a_call_over_the_cap_is_refused_and_recorded(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "LOOP_MAX_CALLS", 3)
    seat = LoopSeat(_case(), calls=[("nope", {})] * 5)
    result, _ = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    assert [c.number for c in result.tool_calls] == [1, 2, 3, 4, 5]  # refused calls count toward the cap
    assert all("is not a brokered tool" in c.refused for c in result.tool_calls[:3])
    assert all("the cap of 3 calls per attempt is reached" in c.refused for c in result.tool_calls[3:])


def test_a_call_after_the_time_cap_is_refused(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "LOOP_SECONDS", 0)
    seat = LoopSeat(_case(), calls=[("lint_run", {"files": [_rtl()]})])
    result, engine = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    assert "the attempt's 0 s cap has passed" in result.tool_calls[0].refused
    assert not any(r.advisory for r in engine.state.tool_runs.values())


@EDA
def test_each_run_is_given_no_more_time_than_the_cap_and_the_attempt_allow(nirmaan_org, fixed_clock, tmp_path,
                                                                         monkeypatch):
    monkeypatch.setattr(harness, "LOOP_CALL_SECONDS", 7)
    seat = LoopSeat(_case(), calls=[("lint_run", {"files": [_rtl()]})])
    _, engine = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    [run] = [r for r in engine.state.tool_runs.values() if r.advisory]
    assert int(run.params["timeout"]) == 7


# --- Every call recorded; in-loop runs advisory; the platform's gate alone judges ------------------------


@EDA
def test_the_seat_reads_its_runs_and_every_call_is_on_the_record(nirmaan_org, fixed_clock, tmp_path):
    broken = (FIFO / "sync_fifo.v").read_text().replace("endmodule", "wire oops = ;\nendmodule")
    case = _case()
    seat = LoopSeat(case, calls=[("lint_run", {"files": [_rtl(broken)]}), ("lint_run", {"files": [_rtl()]}),
                                 ("Bash", {"command": "ls"})])
    runtime = ModelRuntime(seat, runtime_id="loop-seat")
    trial = record_trial(nirmaan_org, case, runtime, replay=False, record="r", trial=1, repo=ROOT,
                         sandbox=tmp_path / "box", clock=fixed_clock, variant=VARIANT)
    (failed, _), (passed, _), (refused, _) = seat.results
    assert "lint.run failed" in failed and "Log excerpt" in failed and "syntax error" in failed
    assert "lint.run passed" in passed and "[run:" in passed and refused.startswith("Refused")
    result = trial.result
    assert [(c.tool, c.succeeded, bool(c.refused)) for c in result.tool_calls] == [
        ("lint_run", False, False), ("lint_run", True, False), ("Bash", None, True)]
    assert trial.harness_variant == VARIANT and result.harness == harness_sha256(variant=VARIANT)
    assert result.passed  # the reference answer, judged by the gates and the held-out checks as always
    gate = {g.run for g in result.gate_runs}
    loop_runs = {r for c in result.tool_calls for r in c.runs}
    assert loop_runs and not gate & loop_runs  # the record's gate runs are the platform's own
    # The call log round-trips through the trial's JSON.
    again = type(trial).model_validate_json(trial.model_dump_json())
    assert again.result.tool_calls == result.tool_calls and isinstance(again.result.tool_calls[0], SeatToolCall)
    # A re-judge replays the recorded answers through the gates and judges: no loop run is made again.
    from nirmaan.evals.records import RecordedAnswers

    rejudged, engine = evaluate(nirmaan_org, case, ModelRuntime(RecordedAnswers(trial.answers), runtime_id="r"),
                                replay=False, repo=ROOT, sandbox=tmp_path / "again", clock=fixed_clock,
                                variant=VARIANT)
    assert rejudged.passed and rejudged.tool_calls == () and not any(r.advisory
                                                                    for r in engine.state.tool_runs.values())


@EDA
def test_an_advisory_run_never_meets_a_requirement_and_the_gate_alone_judges(nirmaan_org, fixed_clock, tmp_path):
    # The seat lints good RTL in the loop, then submits RTL that fails lint and names the passing loop run.
    bad = (FIFO / "sync_fifo.v").read_text().replace("endmodule", "wire oops = ;\nendmodule")

    def answer(completion, results):
        text = completion.text.replace((FIFO / "sync_fifo.v").read_text(), bad)
        run = results[0][0].split("[run:", 1)[1].split("]", 1)[0]
        head, rest = text.split("\n", 1)
        data = json.loads(head)
        data["tool_runs"] = [run]
        return type(completion)(json.dumps(data) + "\n" + rest, completion.model)

    seat = LoopSeat(_case(), calls=[("lint_run", {"files": [_rtl()]})], answer=answer)
    result, engine = _run(nirmaan_org, fixed_clock, tmp_path, seat)
    [loop_run] = [r for r in engine.state.tool_runs.values() if r.advisory]
    assert loop_run.succeeded and not result.submitted and not result.passed
    assert "dropped advisory runs from the loop" in result.detail
    evidence = [e for e in engine.state.evidence.values() if e.tool_run == loop_run.id]
    assert evidence == []  # it never reached the engine
    task = engine.task(result.seat)
    lint = next(r for r in task.evidence_requirements if "lint.run" in r.tools)
    gate = next(e for e in engine.state.evidence.values() if e.task == task.id and e.kind is EvidenceKind.TOOL_RUN
                and engine.state.tool_runs[e.tool_run].tool == "lint.run")
    cited = gate.model_copy(update={"tool_run": loop_run.id, "substantiated": True})
    assert not satisfies(engine.state, cited, lint)  # even cited directly, an advisory run meets nothing
    plain = engine.state.tool_runs[loop_run.id].model_copy(update={"advisory": False})
    state = engine.state.model_copy(update={"tool_runs": {**engine.state.tool_runs, loop_run.id: plain}})
    assert satisfies(state, cited, lint)  # the same run, not advisory, would have met it: the flag decides


def test_an_advisory_run_saves_and_loads_and_a_plain_one_saves_as_before():
    from nirmaan.models import ToolRun

    plain = ToolRun(id="run-1", tool="lint.run", actor="a", task="t", succeeded=True, summary="ok")
    assert "advisory" not in plain.model_dump(mode="json")
    loop = plain.model_copy(update={"advisory": True})
    assert loop.model_dump(mode="json")["advisory"] is True
    assert ToolRun.model_validate(loop.model_dump(mode="json")).advisory


# --- Through Claude Code: the real relay, the socket, the flags ---------------------------------------------


def _fake_claude(tmp_path: Path, calls: list, sleep: float = 0) -> tuple[Path, Path]:
    """A ``claude`` that starts the configured MCP server as Claude Code would, speaks MCP to it, and answers."""
    record = tmp_path / "call.json"
    script = tmp_path / "claude"
    script.write_text(f"""#!{sys.executable}
import json, os, subprocess, sys, time
argv = sys.argv[1:]
config = json.load(open(argv[argv.index("--mcp-config") + 1]))
[(name, server)] = config["mcpServers"].items()
proc = subprocess.Popen([server["command"], *server["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        text=True, env=server["env"])
def rpc(i, method, params):
    proc.stdin.write(json.dumps({{"jsonrpc": "2.0", "id": i, "method": method, "params": params}}) + "\\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())
out = {{"argv": argv, "stdin": sys.stdin.read(), "server": name,
       "no_claude_mds": os.environ.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS")}}
out["init"] = rpc(1, "initialize", {{"protocolVersion": "2025-06-18", "capabilities": {{}}}})
proc.stdin.write(json.dumps({{"jsonrpc": "2.0", "method": "notifications/initialized"}}) + "\\n")
out["list"] = rpc(2, "tools/list", {{}})
out["calls"] = [rpc(3 + n, "tools/call", {{"name": c[0], "arguments": c[1]}}) for n, c in enumerate({calls!r})]
time.sleep({sleep})
proc.stdin.close(); proc.wait()
json.dump(out, open({str(record)!r}, "w"))
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "no answer",
                  "usage": {{}}, "modelUsage": {{}}}}))
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script, record


@EDA
def test_through_claude_code_only_the_brokered_server_and_its_tools_are_loaded(nirmaan_org, fixed_clock, tmp_path):
    script, record = _fake_claude(tmp_path, [["lint_run", {"files": [_rtl()]}], ["Bash", {"command": "id"}]])
    runtime = ModelRuntime(ClaudeCodeLLM(executable=str(script)), runtime_id="claude-code")
    result, engine = evaluate(nirmaan_org, _case(), runtime, replay=False, repo=ROOT, sandbox=tmp_path / "box",
                              clock=fixed_clock, variant=VARIANT)
    call = json.loads(record.read_text())
    argv = call["argv"]
    assert argv[argv.index("--tools") + 1] == ""  # no built-in tool: no shell, file or web tool
    assert "--strict-mcp-config" in argv and call["server"] == harness.LOOP_SERVER
    # --safe-mode would turn the server off (CLI 2.1.325); --restricted and the variable keep user files out.
    assert "--safe-mode" not in argv and "--restricted" in argv and call["no_claude_mds"] == "1"
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    allowed = argv[argv.index("--allowedTools") + 1].split(",")
    assert allowed == [f"mcp__{harness.LOOP_SERVER}__{n}" for n in ("lint_run", "simulator_run", "formal_run",
                                                                      "formal_cover")]
    assert call["init"]["result"]["capabilities"] == {"tools": {}}
    assert [t["name"] for t in call["list"]["result"]["tools"]] == [a.rsplit("__", 1)[1] for a in allowed]
    lint, bash = (c["result"] for c in call["calls"])
    assert not lint["isError"] and "lint.run passed" in lint["content"][0]["text"]
    assert bash["isError"] and "is not a brokered tool" in bash["content"][0]["text"]
    assert [(c.tool, c.succeeded) for c in result.tool_calls] == [("lint_run", True), ("Bash", None)]
    assert [r.tool for r in engine.state.tool_runs.values() if r.advisory] == ["lint.run"]
    assert harness.LOOP_SYSTEM.splitlines()[0] in argv[argv.index("--system-prompt") + 1]


def test_the_loop_command_swaps_safe_mode_for_restricted_and_keeps_every_other_seat_flag():
    seat = ["claude", "-p", *harness.CLAUDE_CODE_FLAGS, "--model", "haiku", "--system-prompt", "--safe-mode"]
    argv, env = loop_command(seat, {"HOME": "/h"})
    assert argv == ["claude", "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
                    "--strict-mcp-config", "--model", "haiku", "--system-prompt", "--safe-mode", "--restricted"]
    assert env == {"HOME": "/h", "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"}
    assert "--bare" not in argv  # --bare never reads the plan login
    assert "--safe-mode" in harness.CLAUDE_CODE_FLAGS  # the default and attempts-3 keep it


def test_through_claude_code_a_seat_past_the_time_cap_is_stopped_and_the_attempt_fails(
        nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "LOOP_SECONDS", 2)
    script, record = _fake_claude(tmp_path, [], sleep=60)
    runtime = ModelRuntime(ClaudeCodeLLM(executable=str(script)), runtime_id="claude-code")
    started = time.monotonic()
    result, engine = evaluate(nirmaan_org, _case(), runtime, replay=False, repo=ROOT, sandbox=tmp_path / "box",
                              clock=fixed_clock, variant=VARIANT)
    assert time.monotonic() - started < 30 and not record.exists()  # killed, never finished
    assert not result.submitted and not result.passed
    assert "the attempt passed its 2 s cap; the seat was stopped" in result.detail
    [model_call] = [c for c in engine.state.model_calls.values() if c.task == result.seat]
    assert not model_call.succeeded


def test_the_cli_names_the_variant(tmp_path):
    from typer.testing import CliRunner

    from nirmaan.cli import app

    ran = CliRunner().invoke(app, ["eval", "run", "--help"])
    assert "tools-in-loop" in ran.output.replace("\n", "").replace(" ", "") or "tools-in-loop" in ran.output
    unknown = CliRunner().invoke(app, ["eval", "run", "--replay", "--harness", "nope", "--cases",
                                       str(ROOT / "evals"), "--repo", str(ROOT), "--out", str(tmp_path / "x")])
    assert "known: default, attempts-3, tools-in-loop" in unknown.output

