# Qortium site

Promotional / explanatory website for **Qortium** — a stripped-down fork of
Qortal Core with a focused QDN home app. Built from the design plan in
[`deep-research-report.md`](./deep-research-report.md).

Content-first static site: **Astro + MDX**, no client JS framework. Restrained
developer-product aesthetic (line-art house mark, monochrome ink + one signal
accent), candid about preview maturity, framing Qortal as *different goals and
tradeoffs* rather than a replacement.

## View the site

- <https://qortium.app> — primary home

Mirrors (the same published site, served from Qortium/Qortal nodes):

- <http://185.207.104.78:24891/render/WEBSITE/Qortium/Qortium>
- <http://146.103.42.59:24891/render/WEBSITE/Qortium/Qortium>
- <https://qortal.link/Qortium>
- <https://qortal.name/Qortium>

## Run locally

```sh
npm install
npm run dev        # http://localhost:4321/Qortium/
```

```sh
npm run build      # static output in dist/
npm run preview    # serve the production build
npm run check      # astro type / diagnostics check
```

The site is configured for a **QDN sub-path deploy** at
`https://qortal.link/Qortium` — see `base: '/Qortium'` in `astro.config.mjs`.
All internal links go through `withBase()` in `src/data/site.ts`; output uses
directory format with trailing-slash URLs (`/Qortium/compare/`) so paths map
straight to `compare/index.html` with no redirect.

## Pages

`/` Overview · `/compare` (the load-bearing comparison) · `/core` · `/home` ·
`/chat` · `/trust` · `/downloads`.

## Editing content / facts

- Nav, links, releases, and the `withBase()` helper live in `src/data/site.ts` —
  the single source of truth. Update `RELEASES` at each preview release.
- Design tokens and every CSS class are in `src/styles/global.css`.
- Shared shell: `src/layouts/BaseLayout.astro` (head/meta/OG/JSON-LD/canonical),
  `src/components/Header.astro`, `Footer.astro`, `Logo.astro`.

## Before launch (open items)

- Set the real production origin in `astro.config.mjs` / `robots.txt` if it is
  not `qortal.link/Qortium`.
- Replace the placeholder OG image (`public/og-default.png`) and add real
  Qortium Home screenshots (the design plan calls for these on Home/Core).
- Confirm the GitHub org/repo URLs in `src/data/site.ts` `LINKS` match the
  published repositories.
