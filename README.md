# AboutMe

The About page at <https://zake7749.github.io/AboutMe/>, generated from data.

The design is Horizon v7.2, delivered as a review package and migrated here for
production. `index.html`, `css/horizon.css` and `js/horizon.js` are **build
output** — edit the sources below and rebuild, never the generated files.

## Build

```bash
python src/build.py
```

Python 3.10+, standard library only. It writes `index.html`, `css/horizon.css`
and `js/horizon.js`. Commit the output: GitHub Pages serves the repository as-is
and does not run the build.

## Where things live

| What | Where |
|---|---|
| Authored content — projects, publications, awards, experience | `data/content.json` |
| Interface chrome — section headings, button labels, month names | `data/ui-strings.json` |
| Layout and palette | `src/styles.css`, `src/theme.css` |
| Progressive enhancement | `src/interactions.js` |
| Hero image and social icons | `assets/` |

`data/ui-contract.json` records the interaction rules the design depends on —
how project cards route clicks, what the prize line may say, how disclosures
behave. Read it before changing markup in `src/build.py`.

This repository is public, so it tracks only what the published site is built
from. The handoff package, its review and QA records, and `data/sources.json` —
the provenance behind each claim, which the build does not read — stay out of
git. `content.json` still carries the `source_ids` that index them.

## Adding Traditional Chinese

The page is locale-aware but only English is complete, so `BUILD_LOCALES` in
`src/build.py` lists `en` alone.

Content fields resolve as `field_zh` → `field_en` → `field`, so Chinese copy is
added alongside the English rather than replacing it. Interface strings come
from the `zh` block of `data/ui-strings.json`.

```bash
python src/build.py --check zh   # lists every string zh still falls back on
```

When that report is empty, add `'zh'` to `BUILD_LOCALES` and rebuild; the
Chinese page is written to `zh/index.html`.

To make Chinese the primary page instead, swap the `out` values in the
`LOCALES` table (`zh` → `index.html`, `en` → `en/index.html`) and adjust each
locale's `prefix`, which is how the page reaches repository-root assets.

## Checks

```bash
python src/test_page.py --theme light
python src/test_page.py --theme dark
python src/test_project_links.py
```

Needs Playwright, BeautifulSoup4 and a Chromium build (Playwright's own by
default; `--chromium` overrides). The page is served over loopback HTTP so its
external assets load the way a reader gets them. Outbound links are recorded and
cancelled in the browser — no third-party page is visited, so a passing run says
nothing about whether those destinations are still up. Reports land in `build/`,
which is not tracked.

## Theme

One page per locale. A short script in `<head>` applies the stored choice before
first paint, falling back to `prefers-color-scheme`; the toggle persists to
`localStorage`. Without scripting the page stays light and the toggle hides
itself.
