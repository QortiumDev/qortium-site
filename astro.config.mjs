// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

// The site is published to QDN and served under a sub-path, e.g.
//   https://qortal.link/Qortium
// so `site` is the gateway origin and `base` is the QDN resource path.
// Because the app lives under a sub-path, NEVER use root-absolute internal
// links ("/why"). Always route links and assets through the `withBase()`
// helper in src/data/site.ts so they resolve correctly on QDN.
export default defineConfig({
  site: 'https://qortal.link',
  base: '/Qortium',
  // Directory output + trailing-slash links: /Qortium/compare/ maps directly to
  // compare/index.html with no redirect, which is the most robust form for
  // static hosts and the QDN renderer alike.
  trailingSlash: 'always',
  integrations: [mdx(), sitemap()],
  build: {
    inlineStylesheets: 'auto',
    format: 'directory',
  },
});
