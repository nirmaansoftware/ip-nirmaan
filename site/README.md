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

The test count (875, the standard run that deselects the SDK test) is not checked automatically; update it by hand when it changes.

## Launch list

Nirmaan runs every website through its launch list
([`docs/engineering/list.md`](https://github.com/nirmaansoftware/Nirmaan/blob/main/docs/engineering/list.md)
in `nirmaansoftware/Nirmaan`). Last run 2026-09-28, before first deploy:

| # | Item | Result |
|---|---|---|
| 1 | Privacy policy | PASS: footer links to nirmaan.online/privacy.html, which covers this site |
| 2 | Terms & conditions | PASS: footer links to nirmaan.online/terms.html; the code is under Apache-2.0 |
| 3 | Frontend secrets | PASS: none; the page has no keys at all |
| 4 | HTTPS | Vercel enforces it; check with `curl -I` after deploy |
| 5 | Cookie banner | N/A: no cookies and no storage |
| 6 | Meta titles / descriptions | PASS: title, description, canonical, `og:url` |
| 7 | Social preview image | PASS: `og-image.png`, 1200x630, with alt text |
| 8 | Favicon | PASS: `favicon.svg` (light and dark) and `apple-touch-icon.png` |
| 9 | Sitemap and robots.txt | PASS |
| 10 | Image alt text | PASS: no `<img>`; the graph SVG has a title, glyphs are `aria-hidden` |
| 11 | Image compression | PASS: largest file is the 52 KB preview image |
| 12 | Page load speed | Lighthouse mobile, local server without compression: performance 84, LCP 3.3 s, CLS 0.005, TBT 0 ms. Re-run on the deployed URL |
| 13 | Color contrast | PASS: Lighthouse accessibility 100 |
| 14 | Mobile responsiveness | PASS: checked at a true 390 px viewport |
| 15 | Custom 404 page | PASS: `404.html` (Vercel serves it with status 404) |
| 16 | Broken links | PASS |
| 17 | Form validation | N/A: no forms |
| 18 | Spam protection | N/A: no forms |
| 19 | Analytics | None, per the brief ("no tracking"). Open for the owner to revisit |
| 20 | Single clear CTA | PASS: "View on GitHub" |

## Deploying

Deploy on Vercel as its own project with **Root Directory** set to `site`
(`vercel.json` here adds the security headers; there is no build step). Add
`ip.nirmaan.online` as the project's domain, then a CNAME record for `ip` on
`nirmaan.online` pointing at `cname.vercel-dns.com`. After it is live, re-run
item 12 and add the URL to `pyproject.toml` and the README (see `docs/ROADMAP.md`).
