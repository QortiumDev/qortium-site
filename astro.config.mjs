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
  site: 'https://qortal.link',
  trailingSlash: 'ignore',
  integrations: [mdx(), sitemap()],
  build: {
    inlineStylesheets: 'auto',
    format: 'file',
    assetsPrefix: '.',
  },
});
