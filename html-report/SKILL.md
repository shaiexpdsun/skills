---
name: html-report
description: >-
  Turns analyses and reports into a standalone HTML page in the browser
  (canal B: black + cold gray only — Cursor-like chrome, no blue, no solid
  white buttons). Never Cursor Canvas. Use when asked for relatório, report,
  HTML report, web brief, site, página, painel, dashboard, análise, plano,
  comparação, stack, lista, or any long view to click or show someone; when
  they mention HTML, design system, or when the canvas skill would otherwise
  create a canvas.
---

# HTML report (not canvas)

Analytical or interactive deliverable = **one standalone HTML file** opened in
the browser. Not `.canvas.tsx`. Copy `<style>` from [tokens.html](tokens.html).
Do not improvise the palette. Do not use gold `#e0a106`, Portal `#0000f2`,
Grok blue `#2d7ff9` / `#3b82f6`, or solid white buttons.

## When

Report, “monta uma página”, “mostra no browser”, plan, stack, comparison,
dashboard, research, long list — anything that would become a markdown table
or essay.

**Not** for: code patch, commit, Obsidian `.md` they asked for, 1–2 paragraph
chat answers.

**Canvas:** only if they deliberately write **canvas**. Otherwise HTML.

## File

Single `.html` (inline CSS + JS). No npm, no React. Google Fonts `@import` in
`<style>` only (Instrument Sans + IBM Plex).

| Context | Folder |
|---|---|
| Default | `./reports/` (create if missing) |
| User named a folder / project | only there |
| Existing project with an `html/` or `reports/` convention | follow that |

Name: kebab-case (`stack-compare.html`, `status-tracks.html`).

In chat: path + one-line summary.

Brand label in the rail: use **Report** unless the user names another brand.

## Design — canal B (cinza only)

Black floor + cold gray chrome (Cursor-like bars/buttons). No accent color.

**Surfaces**

- Chão `#000000` · rail/panel `#0a0a0a` · elev `#141414` · chip `#1c1c1c`
- Text `#e8e8e8` · mute `#a3a3a3` · mute-2 `#737373` · line `#262626`

**Actions (all gray)**

- Primary / Review: `#262626` (`.btn`, `.btn-review`)
- Ghost / outline: transparent + `#333` border (`.btn-ghost`, `.btn-bar`)
- Send circle: `#404040` (`.send`) — not white, not blue

**Chrome**

- `.topbar` · `.composer` (chips) · `.statusbar` · aside `.aside-toolbar`
- Radius ~8–14px

**Type**

- Instrument Sans 500 · IBM Plex Sans · IBM Plex Mono kickers `//`

**Shell**

- Rail chips · main sections · aside file-list
- No card wall, no emoji, no accent color
- One idea per screen

Living reference: [design-system.html](design-system.html) in this folder.

## Page = one scroll. Tabs are exception

Main is one column of `.section`s. Rail = `#id` jump links (scroll-spy).

**New tab only** for a large autonomous block. Prefer `<details>` for minor bits.

## Interaction

- Rail anchors + search/filter on data
- Tables searchable if >8 rows
- Vanilla JS in the same file

## Skeleton

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#000000" />
  <title>TÍTULO</title>
  <style>/* paste tokens.html */</style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <span>&gt; report</span>
      <span class="crumb">html / <b>nome.html</b></span>
      <span class="spacer"></span>
      <button class="btn-review" type="button">Review</button>
    </header>
    <div class="shell">
      <aside class="rail">
        <p class="brand"><span class="mark"></span>Report</p>
        <input type="search" placeholder="Filtrar" />
        <p class="nav-label">Explore</p>
        <nav>
          <a href="#overview" aria-current="true">Overview</a>
          <a href="#lista">Lista</a>
        </nav>
      </aside>
      <main class="main">
        <section id="overview" class="section">
          <p class="kicker">//Overview</p>
          <h1>Título claro, uma ideia.</h1>
          <p class="lede">Uma frase. O ponto.</p>
        </section>
      </main>
      <aside class="aside">
        <div class="aside-toolbar"><span class="path"><b>notes</b></span></div>
        <div class="aside-body">
          <p class="kicker">//Notas</p>
          <h2>O que importa.</h2>
          <div class="file-list">
            <a href="#overview" aria-current="true">overview</a>
          </div>
        </div>
      </aside>
    </div>
    <footer class="statusbar">
      <span class="accent">html-report</span>
      <span>canal B</span>
    </footer>
  </div>
  <script>/* scroll-spy + filter */</script>
</body>
</html>
```

## Content

Lead with the answer. Real data. No CPF/password/PIX. In chat: path + 5–10 line
verdict, not the full table.

See [examples.md](examples.md).
