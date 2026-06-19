// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

// The site is published to QDN and shown through the Core render endpoint
// (/render/WEBSITE/<name>...). That renderer injects a <base href> at the
// resource root and only resolves RELATIVE asset/link paths — any root-absolute
// "/foo" path escapes the resource and 404s. So:
//   - no `base` prefix,
//   - `assetsPrefix: '.'` so bundled assets are referenced relatively (./_astro/…),
//   - `format: 'file'` so every page is a flat file at the resource root
//     (compare.html, core.html, …) and relative links resolve the same from any page.
// All internal links/assets go through `withBase()` in src/data/site.ts, which
// returns relative paths; canonical/OG/JSON-LD use `absUrl()` for absolute URLs.
export default defineConfig({
  // Canonical brand domain (the site is multi-homed across QDN + this domain).
  site: 'https://qortium.app',
  trailingSlash: 'ignore',
  integrations: [
    mdx(),
    // Emit sitemap URLs that match the flat .html files actually built, so the
    // listed URLs resolve on a plain static host and on QDN (format: 'file').
    sitemap({
      serialize(item) {
        const root = 'https://qortium.app';
        if (item.url === root || item.url === root + '/') {
          item.url = root + '/';
        } else if (!/\.[a-z0-9]+$/i.test(new URL(item.url).pathname)) {
          item.url = item.url.replace(/\/$/, '') + '.html';
        }
        return item;
      },
    }),
  ],
  build: {
    inlineStylesheets: 'auto',
    format: 'file',
    assetsPrefix: '.',
  },
});
