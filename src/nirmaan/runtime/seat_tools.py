"""Tools in the loop (M75): the brokered tools a seat calls during its attempt, broker side.

Council record 2026-11-14 (pilot retrospective), decision 4, the first variant (``--harness tools-in-loop``):
the seat calls the platform's own lint, simulation and formal checks while it works, reads what they say,
and then submits. The conditions the decision sets, and where each holds:

* **Brokered tools only, under the seat's role; no shell, file or network tool.** Claude Code runs with
  ``--tools ""`` (no built-in tool), ``--strict-mcp-config`` with one server, this one, and ``--allowedTools``
  naming only its tools, in ``dontAsk`` mode. ``--safe-mode`` would turn that server off too, so the variant
  swaps it for ``--restricted`` and ``CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`` (:func:`loop_command`), which keep
  the person's own settings and instruction files out as well. The server Claude Code starts is a stdio relay
  (``seat_tools_relay.py``, standard library only, started with an empty environment) that holds no tool: it
  hands each request to :class:`SeatTools` over a private socket, and every call runs here, through the seat's
  own :class:`ToolHandle`, so the broker checks the role's grant, the tool's contract and its probe as for any
  run. A seat is offered only the loop tools (``harness.loop_tools()``, company data) the platform runs over
  its own files for this task and its role is granted; any other name is refused, and so is a call when
  nothing is offered.
* **No credential in a tool run's environment.** The tools run through the EDA runner, whose steps see this
  process's environment with every credential removed (M53, ``run_environment``); the relay sees none.
* **Paths limited to the seat's workspace, so held-out files are unreachable.** A call passes file
  contents, never a path to read: each is written under a fresh directory in the seat's workspace, at a
  relative path (``safe_path``), with an HDL or SymbiYosys suffix (``LOOP_SUFFIXES``). The run's own
  directory (``workdir``) is that directory too. The other inputs are the ones the platform's check gets: the
  task's inputs and its approved upstream files. :func:`screen` refuses a file that could reach anything else
  or run anything: a string or token that names an absolute path, a home directory or a parent directory;
  an include of anything but a relative file; a system task that reads or writes files or runs a command
  (``$system``, ``$c``, DPI, ``$fopen``, ``$readmem*``); and, in a ``.sby``, a section, a script command or
  an engine outside a short list (no ``!`` shell line, no ``exec``, ``tee`` or ``script``).
* **A cap on calls and time per attempt, a timeout being a failed attempt.** ``LOOP_MAX_CALLS`` calls,
  refused ones counted; ``LOOP_SECONDS`` from the start of the attempt, model and tools together. Each run's
  own timeout is the least of ``LOOP_CALL_SECONDS``, the time left and the requirement's own. Past the time,
  every call is refused and the claude-code runtime stops the seat: its answer is a failed call
  (:func:`run_with_tools`).
* **Every call recorded.** Each call, refused or not, is a :class:`~nirmaan.models.SeatToolCall` on the
  trial's result; each run is a :class:`~nirmaan.models.ToolRun` in the sandbox, ``advisory``, named
  ``[run:<id>]`` in what the seat reads.
* **In-loop runs advisory; the platform's gate runs alone judge.** An advisory run never meets a
  requirement (``policy.satisfies``), and one the seat lists in ``tool_runs`` is dropped before the engine
  sees it (``ModelRuntime._result``). The checks the platform runs on the submitted files are unchanged.
* **The server code and tool pins in the fingerprint.** ``harness.LOOP_CODE`` (this file and the relay) and
  ``harness.tool_pins()`` are in the variant's fingerprint, with the loop settings.

A call is checked the way the platform checks the files of an answer: the requirements over the seat's own
files that name the tool are run by ``ModelRuntime._postflight`` itself, on the files the call passed,
through an advisory handle. So what the seat sees is what the gate would say of those files.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

from nirmaan.models import EvidenceKind, SeatToolCall
from nirmaan.runtime import harness
from nirmaan.runtime.files import excerpt, safe_path, write_file

_TOOL_BACKED = {EvidenceKind.TOOL_RUN, EvidenceKind.VERITRIAGE_SESSION}
#: The relay Claude Code starts, by path: it imports nothing of this package.
RELAY = Path(__file__).resolve().with_name("seat_tools_relay.py")
_ENTRY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]{0,127}")

# --- The screen ----------------------------------------------------------------------------------

#: A system task or construct that reads or writes a file, or runs code outside the simulation.
_ESCAPES_RE = re.compile(r"(?<![\w$])(?:\$system|\$c(?:pure|\d*)(?=\s*\()|DPI|\$fopen|\$fread|\$fscanf|\$fgets"
                         r"|\$fgetc|\$readmem[hb]|\$writemem[hb]|\$sreadmem[hb])(?![\w$])")
#: A string that starts at the root or a home directory, a parent directory anywhere, or an escaped byte in a
#: string (a way to spell a path the other patterns would see).
_PATHS_RE = re.compile(r"\"\s*[/~]|\.\./|/\.\.(?![\w.])|\\[0-7xX]")
_INCLUDE_RE = re.compile(r"`include\b\s*(?:\"([^\"\n]*)\")?")
#: In a .sby: the sections, the yosys commands of [script], and the engines a proof setup here uses.
_SBY_SECTIONS = ("options", "engines", "script", "files", "tasks")
_SBY_COMMANDS = ("read", "read_verilog", "prep", "chparam", "hierarchy", "proc", "flatten", "opt", "opt_clean",
                 "memory", "chformal", "setattr", "async2sync", "dffunmap", "clk2fflogic", "check")
_SBY_ENGINES = ("smtbmc", "abc", "btor")


def _hdl_problem(path: str, text: str) -> str | None:
    found = _ESCAPES_RE.search(text)
    if found:
        return f"{path} uses {found.group(0)}, which reads or writes files or runs code; refused in the loop"
    for include in _INCLUDE_RE.finditer(text):
        name = include.group(1)
        if not name or not safe_path(name):
            return f"{path} includes {include.group(0).strip()!r}: only a relative file of the call may be included"
    found = _PATHS_RE.search(text)
    if found:
        return (f"{path} names a path outside the call ({found.group(0)!r}): only relative files of the call "
                "may be named")
    return None


def _sby_problem(path: str, text: str) -> str | None:
    found = _PATHS_RE.search(text)
    if found:
        return f"{path} names a path outside the call ({found.group(0)!r})"
    section, inline = None, []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            name = section.removeprefix("file ").strip() if section.startswith("file ") else None
            if section not in _SBY_SECTIONS and not (name and safe_path(name)):
                return f"{path} has a [{section}] section; the loop takes [{'], ['.join(_SBY_SECTIONS)}] only"
            continue
        if (section or "").startswith("file "):
            inline.append(line)  # an inline file's body is HDL: screened as one below
            continue
        if not stripped or stripped.startswith("#"):
            continue
        for token in stripped.split():
            if token.startswith(("/", "~")) or ".." in token:
                return f"{path} names a path outside the call ({token!r})"
        if section == "files" and not all(safe_path(t) for t in stripped.split()):
            return f"{path} lists {stripped!r} in [files]: relative files of the call only"
        if section == "script":
            if stripped.startswith("!"):
                return f"{path} runs a shell command in [script]; refused in the loop"
            for command in filter(None, (c.strip() for c in stripped.split(";"))):
                if command.split()[0] not in _SBY_COMMANDS:
                    return (f"{path} runs {command.split()[0]!r} in [script]; the loop takes "
                            f"{', '.join(_SBY_COMMANDS)}")
        if section == "engines":
            words = stripped.split()
            if words[0] not in _SBY_ENGINES or "--" in words:
                return f"{path} runs the engine {stripped!r}; the loop takes {', '.join(_SBY_ENGINES)}"
    return _hdl_problem(path, "\n".join(inline)) if inline else None


def screen(path: str, content: str) -> str | None:
    """Why a file the seat passes in a call is refused (it could reach a file outside the call, or run code), or None."""
    if Path(path).suffix == ".sby":
        return _sby_problem(path, content)
    return _hdl_problem(path, content)


# --- The session ----------------------------------------------------------------------------------


def mcp_name(tool: str) -> str:
    """The name a tool has in the brokered server: its ID with each dot an underscore."""
    return tool.replace(".", "_")


class SeatTools:
    """One attempt's brokered tools: what is offered, every call, and the caps (broker side).

    ``postflight`` is the runtime's own check of an answer's files (``ModelRuntime._postflight``); a call runs
    it on the files it passes, restricted to the requirements that name the tool, through an advisory handle.
    """

    def __init__(self, packet: Any, tools: Any, inputs: dict[str, str], postflight: Callable, attempt: int,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._packet, self._inputs, self._postflight = packet, dict(inputs), postflight
        self._handle = tools.advisory()
        self.attempt = attempt
        self._clock = clock
        self._started = clock()
        self.calls: list[SeatToolCall] = []
        self._root: Path | None = None
        granted = set(packet.tools)
        specs = {spec.id: spec for spec in packet.task.gates}
        self._offered: dict[str, tuple[str, list, list[str]]] = {}
        for tool in harness.loop_tools():
            reqs = [r for r in packet.task.evidence_requirements
                    if r.files and _TOOL_BACKED & set(r.accepts) and tool in r.tools]
            kinds = list(dict.fromkeys(k for r in reqs for b in r.files if not b.upstream for k in b.kinds))
            if reqs and kinds and tool in granted and tool in specs:
                self._offered[mcp_name(tool)] = (tool, reqs, kinds)
        self._specs = specs

    # What the seat is told and offered.

    def names(self) -> tuple[str, ...]:
        return tuple(self._offered)

    def system_note(self) -> str:
        return harness.LOOP_SYSTEM.format(calls=harness.LOOP_MAX_CALLS, seconds=harness.LOOP_SECONDS)

    def listing(self) -> list[dict[str, Any]]:
        """The brokered server's tools, as MCP tool definitions."""
        out = []
        for name, (tool, _, kinds) in self._offered.items():
            out.append({"name": name, "description": (
                f"{self._specs[tool].description} Runs {tool} through the platform's tool broker on the files you "
                "pass, as the platform runs it over your files for this task. Advisory: the checks on your final "
                f"answer alone judge it. File kinds: {', '.join(kinds)}."),
                "inputSchema": {"type": "object", "additionalProperties": False, "required": ["files"],
                                "properties": {"files": {
                                    "type": "array", "minItems": 1, "maxItems": harness.LOOP_MAX_FILES,
                                    "items": {"type": "object", "additionalProperties": False,
                                              "required": ["path", "kind", "content"], "properties": {
                                                  "path": {"type": "string", "description": "A relative path, as "
                                                           "in a file block, with a suffix of "
                                                           f"{', '.join(harness.LOOP_SUFFIXES)}."},
                                                  "kind": {"type": "string", "enum": kinds},
                                                  "content": {"type": "string"},
                                                  "entry": {"type": "string", "description": "The top module, "
                                                            "as a files entry declares it."}}}}}}})
        return out

    # The caps.

    def remaining(self) -> float:
        return harness.LOOP_SECONDS - (self._clock() - self._started)

    def expired(self) -> bool:
        return self.remaining() <= 0

    # A call.

    def call(self, name: Any, arguments: Any) -> tuple[str, bool]:
        """Run one call; its text for the seat, and whether it is an error. Every call is recorded."""
        started, number = self._clock(), len(self.calls) + 1

        def done(text: str, runs: tuple[str, ...] = (), succeeded: bool | None = None,
                 refused: str | None = None) -> tuple[str, bool]:
            self.calls.append(SeatToolCall(attempt=self.attempt, number=number, tool=str(name)[:200], runs=runs,
                                           succeeded=succeeded, refused=refused,
                                           seconds=round(self._clock() - started, 3)))
            return text, refused is not None or not succeeded

        def refuse(why: str) -> tuple[str, bool]:
            return done(f"Refused, nothing ran: {why}", refused=why)

        if self.remaining() < 1:
            return refuse(f"the attempt's {harness.LOOP_SECONDS} s cap has passed")
        if number > harness.LOOP_MAX_CALLS:
            return refuse(f"the cap of {harness.LOOP_MAX_CALLS} calls per attempt is reached; answer now")
        offered = self._offered.get(name) if isinstance(name, str) else None
        if offered is None:
            known = ", ".join(self._offered) or "none"
            return refuse(f"{str(name)[:100]!r} is not a brokered tool of this seat; the tools are: {known}")
        tool, reqs, kinds = offered
        try:
            files = self._files(arguments, kinds)
        except ValueError as exc:
            return refuse(str(exc))
        root = self._call_dir(number)
        produced = []
        for path, kind, content, entry in files:
            location, digest = write_file(root, path, content)
            produced.append({"kind": kind, "title": path, "summary": "a file passed in the loop", "entry": entry,
                             "location": str(location), "digest": digest})
        notes, _ = self._postflight(self._restricted(tool, reqs, root), self._handle, self._inputs, produced)
        runs = tuple(n.run for n in notes if n.run)
        succeeded = bool(notes) and all(n.run and n.succeeded for n in notes)
        return done(self._report(notes), runs=runs, succeeded=succeeded)

    def _files(self, arguments: Any, kinds: list[str]) -> list[tuple[str, str, str, str | None]]:
        if not isinstance(arguments, dict) or set(arguments) != {"files"}:
            raise ValueError("a call takes one argument, files")
        items = arguments["files"]
        if not isinstance(items, list) or not items:
            raise ValueError("files must be a list of at least one file")
        if len(items) > harness.LOOP_MAX_FILES:
            raise ValueError(f"{len(items)} files; a call takes at most {harness.LOOP_MAX_FILES}")
        out, seen, total = [], set(), 0
        for item in items:
            if not isinstance(item, dict) or not {"path", "kind", "content"} <= set(item) or set(item) - {
                    "path", "kind", "content", "entry"}:
                raise ValueError("each file has a path, a kind, its content, and maybe an entry, nothing else")
            path, kind, content, entry = item["path"], item["kind"], item["content"], item.get("entry")
            if not isinstance(path, str) or not safe_path(path):
                raise ValueError(f"unsafe file path {str(path)[:100]!r}: relative, no '..', ordinary characters")
            if path in seen:
                raise ValueError(f"{path} is passed twice")
            if Path(path).suffix not in harness.LOOP_SUFFIXES:
                raise ValueError(f"{path}: the loop takes {', '.join(harness.LOOP_SUFFIXES)} files only")
            if kind not in kinds:
                raise ValueError(f"{path}: kind {str(kind)[:60]!r} is not one this tool takes ({', '.join(kinds)})")
            if not isinstance(content, str):
                raise ValueError(f"{path}: content must be text")
            if entry is not None and (not isinstance(entry, str) or not _ENTRY_RE.fullmatch(entry)):
                raise ValueError(f"{path}: entry must be a module name")
            total += len(content)
            if total > harness.LOOP_MAX_CHARS:
                raise ValueError(f"the files are over {harness.LOOP_MAX_CHARS} characters together")
            problem = screen(path, content)
            if problem:
                raise ValueError(problem)
            seen.add(path)
            out.append((path, kind, content, entry))
        return out

    def _call_dir(self, number: int) -> Path:
        """A fresh directory for one call, in the seat's workspace (a temporary one when it has none)."""
        if self._root is None:
            base = self._inputs.get("workspace")
            task = re.sub(r"[^A-Za-z0-9._\-]", "_", self._packet.task_id)
            if base:
                self._root = Path(base) / f"{task}.loop"
                self._root.mkdir(parents=True, exist_ok=True)
            else:
                self._root = Path(tempfile.mkdtemp(prefix="nirmaan-loop-"))
        return Path(tempfile.mkdtemp(prefix=f"a{self.attempt}-c{number}-", dir=self._root)).resolve()

    def _restricted(self, tool: str, reqs: list, root: Path) -> Any:
        """The packet with only the requirements that name ``tool``, each run in ``root`` and in the time left."""
        spec = self._specs[tool]
        changed = []
        for req in reqs:
            params = dict(req.params)
            if spec.param("workdir"):
                params["workdir"] = str(root)
            if spec.param("timeout"):
                given = int(params["timeout"]) if str(params.get("timeout", "")).isdigit() else harness.LOOP_CALL_SECONDS
                params["timeout"] = str(max(1, min(harness.LOOP_CALL_SECONDS, int(self.remaining()), given)))
            changed.append(req.model_copy(update={"tools": (tool,), "params": tuple(params.items())}))
        task = self._packet.task.model_copy(update={"evidence_requirements": tuple(changed)})
        return self._packet.model_copy(update={"task": task})

    def _report(self, notes: tuple) -> str:
        left = harness.LOOP_MAX_CALLS - len(self.calls) - 1
        lines = [f"Advisory runs: never evidence. {left} of {harness.LOOP_MAX_CALLS} calls left in this attempt, "
                 f"about {max(0, int(self.remaining()))} s."]
        if not notes:
            lines.append("No check of this tool applies to the files given.")
        for note in notes:
            if note.run is None:
                lines.append(f"{note.tool} not run: {note.summary}")
                continue
            lines.append(f"[run:{note.run}] {note.tool} {'passed' if note.succeeded else 'failed'}: {note.summary}")
            if not note.succeeded:
                run = self._handle.recorded(note.run)
                found, what = excerpt(run.references[0] if run and run.references else None)
                lines.append(f"Log excerpt ({what}):" + "".join(f"\n| {line}" for line in found))
        return "\n".join(lines)


# --- The socket the relay reaches the session through ------------------------------------------------

#: The most bytes one request from the relay may carry.
_MAX_REQUEST = 4 * 1024 * 1024


class Endpoint:
    """A private socket for one attempt, the token the relay must present, and the server config for Claude Code.

    The directory is made by ``mkdtemp`` (mode 0700) outside the seat's working directory; the seat has no file
    tool to read it. The relay is started by ``/usr/bin/env -i`` with this Python in isolated mode, so it sees
    no environment variable and imports nothing but the standard library.
    """

    def __init__(self, session: SeatTools) -> None:
        self.session = session
        self.dir = Path(tempfile.mkdtemp(prefix="nl-"))
        self.token = secrets.token_hex(16)
        token = self.dir / "token"
        token.write_text(self.token, encoding="utf-8")
        token.chmod(0o600)
        self.path = self.dir / "s"
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(self.path))
        self._sock.listen(4)
        self._sock.setblocking(False)
        self._selector = selectors.DefaultSelector()
        self._selector.register(self._sock, selectors.EVENT_READ)
        self.config = self.dir / "mcp.json"
        server = {"type": "stdio", "command": "/usr/bin/env",
                  "args": ["-i", sys.executable, "-I", str(RELAY), str(self.path)], "env": {}}
        self.config.write_text(json.dumps({"mcpServers": {harness.LOOP_SERVER: server}}), encoding="utf-8")

    def flags(self) -> list[str]:
        """The Claude Code flags that load only this server and allow only its tools."""
        allowed = ",".join(f"mcp__{harness.LOOP_SERVER}__{name}" for name in self.session.names())
        return ["--mcp-config", str(self.config), *harness.LOOP_FLAGS, "--allowedTools", allowed]

    def serve(self, timeout: float) -> bool:
        """Answer at most one request, waiting up to ``timeout`` seconds; whether one came."""
        if not self._selector.select(timeout):
            return False
        try:
            conn, _ = self._sock.accept()
        except (BlockingIOError, InterruptedError):
            return False
        with conn:
            conn.setblocking(True)
            conn.settimeout(10)
            try:
                reply = self.handle(_read_line(conn))
            except (OSError, ValueError) as exc:
                reply = {"error": f"bad request: {type(exc).__name__}"}
            try:
                conn.sendall(json.dumps(reply).encode("utf-8") + b"\n")
            except OSError:
                pass
        return True

    def handle(self, raw: bytes) -> dict[str, Any]:
        """One request from the relay: ``{"token", "method", "params"}``; the reply it hands back."""
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict) or not secrets.compare_digest(str(request.get("token", "")), self.token):
            return {"error": "refused: not this attempt's relay"}
        method, params = request.get("method"), request.get("params") or {}
        if method == "tools/list":
            return {"result": {"tools": self.session.listing()}}
        if method == "tools/call" and isinstance(params, dict):
            text, error = self.session.call(params.get("name"), params.get("arguments"))
            return {"result": {"content": [{"type": "text", "text": text}], "isError": error}}
        return {"error": f"unknown method {str(method)[:60]!r}"}

    def close(self) -> None:
        self._selector.close()
        self._sock.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self) -> "Endpoint":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _read_line(conn: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
        if len(data) > _MAX_REQUEST:
            raise ValueError("request too large")
    return data


def _pump_in(pipe: Any, text: str) -> None:
    try:
        pipe.write(text)
    except (BrokenPipeError, OSError, ValueError):
        pass
    finally:
        try:
            pipe.close()
        except (BrokenPipeError, OSError):
            pass


def _pump_out(pipe: Any, into: list[str]) -> None:
    into.append(pipe.read())


def _stop(proc: subprocess.Popen) -> None:
    """Kill the seat and everything it started (the relay), by its process group."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


def loop_command(argv: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """The seat's Claude Code command and environment for the variant (harness ``LOOP_DROPPED_FLAGS``,
    ``LOOP_ISOLATION_FLAGS``, ``LOOP_ENV``): ``--safe-mode`` out, since it turns off the brokered server too,
    and ``--restricted`` and ``CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`` in, so no user-level file reaches the seat.
    The value of ``--model`` or ``--system-prompt`` is never read as a flag."""
    kept = [arg for i, arg in enumerate(argv)
            if arg not in harness.LOOP_DROPPED_FLAGS or (i and argv[i - 1] in ("--model", "--system-prompt"))]
    return [*kept, *harness.LOOP_ISOLATION_FLAGS], {**env, **dict(harness.LOOP_ENV)}


def run_with_tools(argv: list[str], user: str, cwd: str, env: dict[str, str], session: SeatTools,
                   timeout: float) -> tuple[int | None, str, str, str | None]:
    """Run Claude Code with the brokered server, serving its calls in this thread until it answers.

    Returns the exit status, stdout, stderr, and why the seat was stopped (None when it answered): past
    ``timeout`` or the attempt's cap the seat is killed and the attempt fails. Calls are served in the calling
    thread, which holds the project's writer, so every advisory run is recorded in turn.
    """
    argv, env = loop_command(argv, env)
    with Endpoint(session) as endpoint:
        proc = subprocess.Popen([*argv, *endpoint.flags()], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=cwd, env=env, start_new_session=True)
        out: list[str] = []
        err: list[str] = []
        pumps = [threading.Thread(target=_pump_in, args=(proc.stdin, user), daemon=True),
                 threading.Thread(target=_pump_out, args=(proc.stdout, out), daemon=True),
                 threading.Thread(target=_pump_out, args=(proc.stderr, err), daemon=True)]
        for pump in pumps:
            pump.start()
        deadline = time.monotonic() + timeout
        stopped = None
        while proc.poll() is None:
            if session.expired():
                stopped = f"the attempt passed its {harness.LOOP_SECONDS} s cap; the seat was stopped"
            elif time.monotonic() > deadline:
                stopped = f"Claude Code did not answer within {int(timeout)}s; the seat was stopped"
            if stopped:
                _stop(proc)
                break
            endpoint.serve(0.2)
        proc.wait()
        for pump in pumps:
            pump.join(timeout=10)
    return proc.returncode, "".join(out), "".join(err), stopped
