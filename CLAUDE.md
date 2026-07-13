# CLAUDE.md

Guidance for AI assistants working in this repository.

## What this is

Static marketing/community website for **DAOP APS** ("Dove Andiamo Oggi Papi"),
a non-profit association for families in the provinces of Alessandria (AL) and
Asti (AT), Italy. Live at **https://www.daop.it** (see `CNAME`).

Content is in **Italian** — keep all user-facing text, and ideally comments and
commit messages, in Italian to match the existing codebase.

There is **no build step and no framework**. Each page is a hand-written,
self-contained HTML file with inline `<style>` and `<script>`. The only
"build" is a nightly Python script that regenerates the events page from a
Google Sheet (see below).

## Tech stack & deployment

- **Plain HTML5 + CSS + vanilla JS.** No npm, no bundler — there is no
  `package.json`, `requirements.txt`, or `Makefile`.
- **Hosting:** GitHub Pages, served straight from the repo root on the default
  branch. `.nojekyll` disables Jekyll processing; `CNAME` sets the custom
  domain. **A merge to the default branch is the deploy** — anything committed
  goes live.
- **Fonts:** Google Fonts (`DM Sans`, `Playfair Display`) loaded via `<link>`.
- **Analytics:** Google Analytics 4 (`G-6M747985MC`), loaded **only after**
  cookie consent — see `assets/js/cookie-consent.js`.
- **Python** is used only by the events generator (`scripts/genera_eventi.py`),
  which relies on the **standard library only** (no third-party packages).

## Repository layout

```
/                     site root (each *.html is a live page)
├── index.html        home page (largest, hand-edited)
├── eventi.html       events listing — MOSTLY GENERATED, see below
├── ginetto.html      "Ginetto AI" product page
├── bollino.html      "Bollino Consigliato DAOP" family-friendly badge
├── piattosano.html   "Il Piatto Sano" educational game (S.A.N.E. Italia)
├── libri.html        books by Patrick Orlando
├── media.html        press / media coverage
├── privacy.html      privacy policy
├── cookypolicy.html  cookie policy (note the spelling: "cooky")
├── grazie.html       form thank-you page
├── 404.html          custom not-found page
├── CNAME             custom domain (www.daop.it)
├── .nojekyll         disable Jekyll on GitHub Pages
├── robots.txt        SEO + AI-bot rules
├── sitemap.xml       sitemap (eventi.html lastmod bumped by the generator)
├── assets/
│   ├── images/       site imagery (logos, people, covers)
│   ├── eventi/       event poster images ("locandine") — see its README.md
│   └── js/
│       └── cookie-consent.js   the only shared external JS file
├── data/
│   └── eventi.json   committed snapshot of events (generator fallback + output)
├── scripts/
│   └── genera_eventi.py   nightly events generator
└── .github/workflows/
    └── aggiorna-eventi.yml   scheduled workflow that runs the generator
```

## The events pipeline (important — read before touching `eventi.html`)

Events come from a **Google Sheet** (tab "Eventi"), not from hand-editing.

1. `scripts/genera_eventi.py` fetches rows from the sheet (live gviz CSV export,
   with a cache-buster; falls back to `data/eventi.json` if the network fails).
2. It filters to future events in provinces **AL/AT**, sorts them, and
   regenerates:
   - the `.events-grid` and category filter chips in **`eventi.html`**,
   - the JSON-LD `schema.org/Event` block in `eventi.html`,
   - the "Prossimi eventi" carousel in **`index.html`** (between the
     `<!-- HOME-EVENTI:START -->` / `<!-- HOME-EVENTI:END -->` markers),
   - the committed snapshot `data/eventi.json`,
   - the `<lastmod>` for `eventi.html` in `sitemap.xml`.
3. `.github/workflows/aggiorna-eventi.yml` runs it nightly (02:00 UTC) and on
   manual dispatch, committing only if `eventi.html`/`index.html`/`eventi.json`
   actually changed.

**Consequences for editing:**
- **Do NOT hand-edit the generated regions** of `eventi.html` (the events grid,
  category filter chips, or the `id="eventi-jsonld"` script) or the
  `HOME-EVENTI` block in `index.html` — the nightly run will overwrite them.
- To change event *content*, edit the Google Sheet, not the HTML.
- To change event *layout/markup*, edit the templates inside
  `scripts/genera_eventi.py` (`render`, `render_home`, `event_jsonld`), then
  run the script to regenerate.
- The generator finds its regions by regex "anchors". If you rename/remove the
  surrounding markers (`event-filters data-group="category"`, `events-grid`
  `id="events-grid"`, `id="eventi-jsonld"`, or the `HOME-EVENTI` comments), the
  script will exit with an error. Keep those markers intact.
- Event poster images live in `assets/eventi/`; the sheet's `Locandina` column
  holds either a filename (resolved to `/assets/eventi/<file>`) or a full URL.
  See `assets/eventi/README.md`.

Run the generator locally with:

```bash
python scripts/genera_eventi.py
```

(No dependencies to install; Python 3.12 is what CI uses.)

## Page conventions (for hand-edited pages)

Every page follows the same self-contained pattern — mirror it when creating or
editing pages:

- `<!DOCTYPE html>` with `<html lang="it">`.
- **All CSS is inline** in `<style>` blocks (typically two per page); there is
  no shared stylesheet. Colors, spacing, and the nav/footer are duplicated
  per page by design — if you change shared chrome (nav, footer, cookie
  banner styling), update each page consistently.
- **The nav and footer are copy-pasted** into each page (no include system).
  The nav links to the top-level pages; keep the link list in sync across pages.
- **Cookie consent + GA** are wired the same way on every page: include
  `assets/js/cookie-consent.js`, then the `gtag` bootstrap. GA must never load
  before consent (Consent Mode v2 defaults everything to `denied`).
- **SEO is taken seriously.** Each page has `<title>`, meta description,
  canonical URL, Open Graph, Twitter Card, and JSON-LD structured data. When
  adding or renaming a page, also update `sitemap.xml` and any nav links.
- Brand palette (recurring hex): orange `#e8954a`/`#d4793a`, deep blue-teal
  `#2d4a5c`, cream background `#fdf8f3`.

## robots.txt / AI-bot policy

`robots.txt` deliberately **blocks AI *training* crawlers** (GPTBot,
Google-Extended, CCBot, ClaudeBot, anthropic-ai, Meta-ExternalAgent, …) while
**allowing citation/retrieval bots** (OAI-SearchBot, ChatGPT-User,
PerplexityBot) and all standard search engines. Preserve this distinction if
you touch `robots.txt`.

## Local preview

`.claude/launch.json` defines a static server config. To preview locally:

```bash
npx http-server -p 8090 -c-1
```

Then open http://localhost:8090. Any static file server works; there's nothing
to compile.

## Git workflow

- The default branch is `main`; **pushing to it deploys the live site.** Do
  routine work on a feature branch and only merge deliberately.
- Automated events commits are authored by `github-actions[bot]` with the
  message "Aggiornamento automatico eventi" (or a "Locandine eventi" message
  from the poster downloader). Don't be surprised by these; don't imitate them
  for manual work.
- Keep commits focused; write messages in Italian to match history.

## Quick checklist when making changes

- Editing event data? → Google Sheet, not the HTML.
- Editing event markup? → `scripts/genera_eventi.py`, then re-run it.
- Adding/removing a page? → update nav on **every** page, `sitemap.xml`, and
  internal links.
- Touching tracking/cookies? → keep GA gated behind consent.
- Any change? → remember there's no build; the committed files are exactly what
  ships.
