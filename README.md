# Playing in New York

A static, typographic five-day cinema calendar built from the supplied designs.

## Interface

`dist/index.html`, `dist/styles.css`, and `dist/app.js` are the complete front end. No build step is needed. Serve `dist` through any static HTTP host. Asset URLs are relative so GitHub project Pages works.

The normal view displays source-attributed listings. `?view=design` displays the supplied example films and festivals, explicitly labeled as sample listings. That mode is for comparing layout with the September 6, 2026 mockups; its programs are not verified. The extra repeated Film Forum examples reproduce the design only. Real listings are deduplicated.

Eight multi-select venue chips; no selected chips means all venues. Hover or keyboard focus on a chip displays the address. Theater headings inside the calendar are plain text, set uppercase in CSS from title-case venue names; the filter chips use those names as written. Date headings scale with column width, capped at 22px. Each date scrolls independently; five-day navigation uses equal-size outlined arrow circles with vertical NEXT and PREVIOUS labels at the top and bottom of the side rail; PREVIOUS is disabled at today, with horizontal single-day swiping on mobile. Hovering or keyboard-focusing a film underlines its full entry and floats an AI-authored, cached two-line film summary and representative image above the text. The black caption bar and image overlap neighboring columns without moving content. It clears on scroll, resize, Escape, or pointer exit. Missing or failed images leave the underline intact without a broken-image placeholder. Film links and series links open official pages in another tab.

Courier Prime is self-hosted. The sans face is Arial, with Helvetica and the generic sans-serif behind it; nothing is downloaded for it. All Arial on the site is tracked at 0.01em, declared universally so it resolves against each element's own size and reaches form controls, which do not inherit tracking. Courier sets its own tracking and is unaffected.

## Data and known coverage limits

`dist/data/screenings.json` contains the last collected snapshot, per-venue status, actual successful-fetch timestamps, official program URLs, and festivals. The scraper uses public HTML or the public endpoint used by each venue's site; it does not bypass access controls.

Metrograph, Film Forum, IFC, Roxy, Quad, BAM, Anthology, and Light Industry are aggregated. Film at Lincoln Center, MoMA, Angelika, Paris, Museum of the Moving Image, and Spectacle are not aggregated and are excluded from filters, columns, and refreshes. Shout-case film titles are normalized to title case. Locally cached film stills retain source attribution in film-images.json.

Only metadata actually present on a source is emitted. Some sources omit director, year, or format; those fields are absent, never guessed. Film Forum's unmarked clock convention is interpreted as daytime/evening cinema times: 10–11 AM, 12 noon, 1–9 PM. Explicit AM/PM overrides this convention. Paris special events may include a Q&A; the linked theater page provides the event details.

Failure retains previous successful listings and the previous successful-fetch timestamp for that venue. An empty parser result is a failure unless the venue's calendar can positively establish no announced events. A failed refresh of every venue does not change the global successful-update timestamp. Normalization merges same-title, same-venue, same-date, same-format showtimes and keeps distinct physical-format presentations separate.

## Refresh

Requires Python 3.12 or newer:

```sh
python -m pip install -r scrapers/requirements.txt
python scrapers/refresh.py
python scrapers/validate.py
```

`--source-dir` can reuse previously downloaded source HTML for reproducible parser checks. It is a development option, not used by the scheduled workflow.

The included GitHub Actions workflow requests a refresh at 8:00 AM America/New_York every day, including daylight-saving changes, then commits the snapshot and deploys `dist` with GitHub Pages. It also supports a manual refresh and publishes front-end edits pushed to main. GitHub scheduling can be delayed; the displayed timestamp always reflects actual collection time. [GitHub scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

The workflow is prepared, not activated: this project must first be placed in the owner's GitHub repository and Pages configured to deploy through GitHub Actions. The private Sites publication is a snapshot and does not itself run the GitHub workflow. Connecting GitHub and selecting a repository are outstanding deployment steps; source access gaps above must also be resolved before claiming comprehensive daily coverage.

Caption summaries live in `dist/data/film-summaries.json`, keyed by screening title. They are written during the morning refresh, not on hover, and committed with the snapshot, so each title is paid for once and can be edited by hand afterwards; an existing entry is never overwritten. `scrapers/summaries.py` asks for one sentence per new title, grounded in that screening's collected description, and keeps a reply only if it is a single sentence of at most 68 characters that splits at a word boundary into two lines of at most 34 — the width the caption box actually holds from 360px up. Below 360px the caption alone steps down a size so both lines stay whole. A caption refused only for its measure is handed straight back with the miss named and rewritten once; anything still short of the mark is retried at the next refresh. Set `ANTHROPIC_API_KEY` as a repository secret to enable it, and optionally the `SUMMARY_MODEL` repository variable to choose the model; without the key the step is skipped and those films show the still with no caption. New titles require a summary entry; raw scraped descriptions are never substituted. Each sentence must admit a word-boundary split into two lines of at most 30 characters, preserving the shared Courier size even on a 320px viewport. Captions use two explicit lines and equal 9px vertical padding.


## Automatic image sourcing

The morning refresh preserves usable cached stills, tries higher-resolution theater images, and then queries TMDB for missing/low-resolution stills. A usable cached image must decode successfully and be at least 500×250 pixels. TMDB candidates must be text-free backdrops at least 720×400, match the normalized title and available year/director, and resolve to a single film. Ambiguous matches remain unresolved. Results are downloaded locally with provenance in film-images.json. image-issues.json lists unresolved pages; they are retried at the next refresh. This checks pixel dimensions and file integrity, not perceived sharpness or artistic quality.

Add your TMDB API Read Access Token to GitHub Settings → Secrets and variables → Actions as TMDB_READ_TOKEN. The workflow passes it only to the Python refresh process, never to browser code. Without it, theater-image downloading continues but TMDB searches are skipped. A live TMDB request has not been tested with your account; mocked matching tests are included in scrapers/tests.

Before enabling TMDB, follow its attribution requirements: use an approved TMDB logo in the application's Credits/About section and the notice “This product uses the TMDB API but is not endorsed or certified by TMDB.” Approved assets: https://www.themoviedb.org/about/logos-attribution . API documentation: https://developer.themoviedb.org/docs/faq .
