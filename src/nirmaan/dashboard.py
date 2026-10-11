"""Self-contained HTML organization dashboard (no JavaScript, no external assets).

Everything shown is a projection of the status report and project state, so
the page cannot disagree with the engine.
"""

from __future__ import annotations

from jinja2 import Environment, select_autoescape

from nirmaan.models import ProjectState, TaskKind
from nirmaan.org import Organization
from nirmaan.work.management import status_report

_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ org_name }} dashboard</title>
<style>
:root { --bg:#f7f7f5; --panel:#ffffff; --ink:#1d1d1b; --muted:#6b6b66; --line:#e3e3de;
  --good:#1f7a4d; --warn:#9a6700; --bad:#b42318; --accent:#2f5bd3; }
@media (prefers-color-scheme: dark) { :root { --bg:#121212; --panel:#1c1c1c; --ink:#ececea; --muted:#a3a39e;
  --line:#2e2e2c; --good:#4cc38a; --warn:#e3b341; --bad:#f97066; --accent:#7ea2ff; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.5 system-ui, -apple-system, sans-serif; }
main { max-width:1200px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:22px; margin:0 0 4px; } h2 { font-size:16px; margin:28px 0 8px; }
.muted { color:var(--muted); }
.tiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin-top:16px; }
.tile { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; }
.tile b { display:block; font-size:22px; }
.scroll { overflow-x:auto; }
table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); }
th, td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-weight:600; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
.pill { display:inline-block; padding:0 8px; border-radius:999px; border:1px solid var(--line); font-size:12px; }
.completed, .approved { color:var(--good); } .blocked, .failed, .escalated { color:var(--bad); }
.in_review, .changes_requested, .in_progress { color:var(--warn); } .ready { color:var(--accent); }
ul { margin:4px 0; padding-left:18px; }
</style></head>
<body><main>
<h1>{{ report.name }}</h1>
<div class="muted">{{ org_name }} &middot; {{ report.project }} &middot; intent {{ report.intent }} &middot;
  audit trail {{ report.audit_entries }} entries</div>
<div class="tiles">
  <div class="tile"><b>{{ (report.progress * 100) | round | int }}%</b>complete</div>
  <div class="tile"><b>{{ report.tasks }}</b>tasks</div>
  <div class="tile"><b>{{ report.active_teams | length }}</b>active teams</div>
  <div class="tile"><b>{{ report.blocked | length }}</b>blocked</div>
  <div class="tile"><b>{{ report.escalations | length }}</b>open escalations</div>
  <div class="tile"><b>{{ report.pending_reviews | length }}</b>pending reviews</div>
  <div class="tile"><b>{{ report.gates | length }}</b>signoff gates</div>
  <div class="tile"><b>{{ report.risks | length }}</b>risks</div>
</div>

<h2>Assurance ladder</h2>
<p class="muted">Planned is not executed, executed is not verified, verified is not approved.</p>
<div class="tiles">{% for k, v in report.assurance.items() %}<div class="tile"><b>{{ v }}</b>{{ k }} artifacts</div>{% endfor %}</div>

{% if report.assumptions %}<h2>Assumptions awaiting an answer</h2><ul>
{% for a in report.assumptions %}<li><b>{{ a.id }}</b>: {{ a.note }} <span class="muted">Q: {{ a.question }}</span></li>{% endfor %}
</ul>{% endif %}

<h2>Workstreams</h2><div class="scroll"><table><tr><th>Phase</th><th>Lead</th><th>Status</th><th>Tasks</th></tr>
{% for ws in workstreams %}<tr><td>{{ ws.phase }}</td><td>{{ ws.lead }}</td><td class="{{ ws.status }}">{{ ws.status }}</td>
<td>{% for k, v in ws.counts.items() %}<span class="pill {{ k }}">{{ k }} {{ v }}</span> {% endfor %}</td></tr>{% endfor %}
</table></div>

<h2>Signoff gates</h2><div class="scroll"><table><tr><th>Gate</th><th>Approver</th><th>Human</th><th>Status</th></tr>
{% for g in report.gates %}<tr><td>{{ g.title }}</td><td>{{ g.approver }}</td><td>{{ "yes" if g.human_required else "no" }}</td>
<td class="{{ g.status }}">{{ g.status }}</td></tr>{% endfor %}</table></div>

{% if report.blocked %}<h2>Blocked, and why</h2>{% for b in report.blocked %}<p><b>{{ b.title }}</b></p><ul>
{% for line in b.why %}<li>{{ line }}</li>{% endfor %}</ul>{% endfor %}{% endif %}

{% if report.escalations %}<h2>Open escalations</h2><div class="scroll"><table><tr><th>ID</th><th>Kind</th><th>To</th><th>Reason</th></tr>
{% for e in report.escalations %}<tr><td>{{ e.id }}</td><td>{{ e.kind }}</td><td>{{ e.to }}</td><td>{{ e.reason }}</td></tr>{% endfor %}
</table></div>{% endif %}

{% if report.pending_reviews %}<h2>Pending reviews</h2><div class="scroll"><table><tr><th>Task</th><th>Reviewer</th><th>Approver</th><th>State</th></tr>
{% for r in report.pending_reviews %}<tr><td>{{ r.title }}</td><td>{{ r.reviewer }}</td><td>{{ r.approver }}</td><td>{{ r.state }}</td></tr>{% endfor %}
</table></div>{% endif %}

<h2>Tasks</h2><div class="scroll"><table><tr><th>Task</th><th>Owner</th><th>Reviewer</th><th>Status</th><th>Risk</th></tr>
{% for t in tasks %}<tr><td>{{ t.title }}</td><td>{{ t.owner }}</td><td>{{ t.reviewer }}</td>
<td class="{{ t.status }}">{{ t.status }}</td><td class="muted">{{ t.risk }}</td></tr>{% endfor %}</table></div>
</main></body></html>
"""


def render_dashboard(org: Organization, state: ProjectState) -> str:
    report = status_report(org, state)
    title = lambda r: org.roles[r].title if r and r in org.roles else "-"  # noqa: E731
    workstreams = []
    for ws in (t for t in state.tasks.values() if t.kind is TaskKind.WORKSTREAM):
        counts: dict[str, int] = {}
        for kid in (t for t in state.tasks.values() if t.parent == ws.id):
            counts[kid.status.value] = counts.get(kid.status.value, 0) + 1
        workstreams.append({"phase": ws.phase, "lead": title(ws.owner), "status": ws.status.value, "counts": counts})
    tasks = [
        {"title": t.title, "owner": title(t.owner), "reviewer": title(t.reviewer), "status": t.status.value,
         "risk": t.risk}
        for t in state.tasks.values()
        if t.kind in (TaskKind.WORK, TaskKind.DECISION, TaskKind.GATE)
    ]
    env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))
    return env.from_string(_TEMPLATE).render(
        org_name=org.name, report=report, workstreams=workstreams, tasks=tasks
    )
