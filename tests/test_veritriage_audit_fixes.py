"""M55: the VeriTriage findings of the read-only audit, each pinned by a test.

H1, a cached project model is rebuilt when its sources changed; M1 and M2, the
RTL provider no longer reads a ``virtual interface`` or a function's return type
as structure; M3, the Wishbone and OCP concepts stay on their own protocols;
and the small items after them.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from veritriage.cli.main import app
from veritriage.project.providers.rtl import parse_rtl
from veritriage.workspace import WorkspaceServices

runner = CliRunner()


def _top(rtl, leaf: str) -> None:
    (rtl / "top.v").write_text(f"module top(input clk);\n  {leaf} u_x (.clk(clk));\nendmodule\n")


# --- H1: a stale cached project model is rebuilt -----------------------------


def test_an_edited_rtl_file_makes_the_cached_model_stale(tmp_path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    _top(rtl, "leaf_a")
    services = WorkspaceServices(project_root=tmp_path / "project")
    services.build_project_model(rtl)
    assert services.load_project_model(rtl) is not None  # fresh: the cache is used
    _top(rtl, "leaf_b")
    assert services.load_project_model(rtl) is None  # stale: the caller rebuilds


def test_analyze_reports_the_modules_of_the_edited_rtl(tmp_path, fixture_log, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the CLI keeps its project cache under the cwd
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    _top(rtl, "leaf_a")

    def modules() -> list[str]:
        out = tmp_path / "out"
        runner.invoke(app, ["analyze", str(fixture_log("axi_timeout.log")), "-o", str(out),
                            "--db", str(tmp_path / "r.db"), "--context-root", str(rtl),
                            "--no-history"])
        data = json.loads((out / "analysis.json").read_text())
        return [m["name"] for m in data["project"]["dut"]["modules"]]

    assert modules() == ["leaf_a", "top"]
    _top(rtl, "leaf_b")
    assert modules() == ["leaf_b", "top"]


# --- M1: a virtual interface is a handle, not a declaration -------------------


def test_a_virtual_interface_in_a_class_does_not_hide_the_next_module():
    parsed = parse_rtl("""
package tb_pkg;
  class drv;
    virtual interface axi_if vif;
    virtual axi_if vif2;
  endclass
endpackage
module top(input clk);
  child u_child (.clk(clk));
endmodule
interface real_if; logic a; endinterface
""", "tb.sv")
    assert dict(parsed.defined) == {"top": "tb.sv"}
    assert dict(parsed.parents) == {"child": "top"}
    assert list(parsed.interfaces) == ["real_if"]


# --- M2: a function's return type is not a module instance --------------------


def test_a_function_returning_a_user_type_is_not_an_instance():
    parsed = parse_rtl("""
module top(input clk);
  function automatic my_t compute(input int x);
    return x;
  endfunction
  function pkg::word_t pick(input int x); return x; endfunction
  leaf u_leaf (.clk(clk));
endmodule
""", "top.sv")
    assert dict(parsed.parents) == {"leaf": "top"}
