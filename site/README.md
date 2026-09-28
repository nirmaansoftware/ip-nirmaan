# ip.nirmaan.online

The IP Nirmaan landing page. Built from `docs/LANDING_PAGE_BRIEF.md`.

Three files and a favicon, no build step, no dependencies, no tracking:

| File | Role |
|---|---|
| `index.html` | All content. Every number and every line of the plan is in the HTML, so the page is complete without JavaScript. |
| `styles.css` | The Nirmaan design system (shared with nirmaan.online), plus a `motion` layer. |
| `motion.js` | Plays the motion. It only animates toward what the HTML already says; it never supplies content. |

## Preview

```
python3 -m http.server 8765 --directory site
```

Then open http://localhost:8765/. To see the still version, turn on
"Reduce motion" in the OS accessibility settings.

## Motion

Motion shows structure, plays once, and is off under `prefers-reduced-motion`.
The page sets `html.motion` only when JavaScript runs and there is no reduced-motion
preference, and every animated rule is scoped to it (a test checks this).

| Piece | What moves | Why |
|---|---|---|
| Hero | Headline rises line by line; the command is typed, then the plan prints line by line and each GATE stamps in | It is the product's real output, arriving the way it does in a terminal |
| Assurance ladder | A token climbs planned, executed, verified, approved; each rung latches as it arrives; then a self-approval is refused | "Planned is not done" and "an AI cannot approve its own work", shown rather than told |
| How it works | The line is drawn and the five steps light in order | A flow, read in order |
| Organization | Stats count up to their real values; the org chart's root lands, the trunk draws, divisions drop in | Built from the top down, like the org itself |
| VeriTriage | Inputs appear, edges draw, evidence nodes land, the top cause fills | Evidence first, conclusion last. Captioned as an illustration |

The terminal and the ladder have a Replay button.

## Rules (enforced by `tests/test_landing_site.py`)

- Stat tiles match `build_organization().stats()` and the Knowledge Pack registry.
- Constitution cards match `CONSTITUTION`, same IDs in the same order.
- No em or en dashes, no hype words, no claims the project cannot back.

The test count (870, the standard run that deselects the SDK test) is not checked automatically; update it by hand when it changes.

## Deploying

Any static host works; point it at this folder. Then add a CNAME record for
`ip` on `nirmaan.online` pointing at the host, and add the URL to
`pyproject.toml` and the README (see `docs/ROADMAP.md`).
