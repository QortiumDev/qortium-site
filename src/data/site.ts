/* ============================================================================
   Qortium site — shared data + helpers (single source of truth)
   Every page/component imports from here. Do not hardcode nav, URLs, or repo
   links in pages.
   ========================================================================== */

/** Astro injects the configured `base` ("/Qortium/") here at build time. */
const BASE = import.meta.env.BASE_URL; // e.g. "/Qortium/"

/**
 * Build a base-aware internal link. The site is served from a QDN sub-path
 * (https://qortal.link/Qortium), so internal links MUST go through this — a
 * root-absolute "/why" would break on the gateway.
 *   withBase('/')      -> "/Qortium/"
 *   withBase('/why')   -> "/Qortium/why"
 *   withBase('img.svg')-> "/Qortium/img.svg"
 */
export function withBase(path = '/'): string {
  const b = BASE.endsWith('/') ? BASE.slice(0, -1) : BASE;
  if (!path || path === '/') return b + '/';
  let p = path.startsWith('/') ? path : '/' + path;
  // Route links get a trailing slash (directory output: /compare/ ->
  // compare/index.html). Asset paths with a file extension are left as-is.
  const lastSeg = p.split('/').pop() ?? '';
  if (!lastSeg.includes('.') && !p.endsWith('/')) p += '/';
  return b + p;
}

export const SITE = {
  name: 'Qortium',
  tagline: 'A cleaner chain baseline with a focused QDN home',
  description:
    'Qortium is a stripped-down fork of Qortal Core with a companion app for wallets, nodes, and QDN browsing. Built for preview testing, chain experimentation, and an explicit roadmap.',
  /** Gateway origin; canonical/OG URLs are origin + base + path. */
  origin: 'https://qortal.link',
  ogImage: '/og-default.png', // relative to base
} as const;

/** Primary navigation (label + internal path). */
export const NAV: { label: string; href: string }[] = [
  { label: 'Why Qortium', href: '/why' },
  { label: 'Qortium vs Qortal', href: '/compare' },
  { label: 'Core', href: '/core' },
  { label: 'Home', href: '/home' },
  { label: 'Downloads', href: '/downloads' },
  { label: 'Docs', href: '/docs' },
  { label: 'FAQ', href: '/faq' },
];

/** External repositories / sources. Keep these as the only place URLs live. */
export const LINKS = {
  coreRepo: 'https://github.com/QortiumDev/qortium-core',
  homeRepo: 'https://github.com/QortiumDev/qortium-home',
  coreReleases: 'https://github.com/QortiumDev/qortium-core/releases',
  homeReleases: 'https://github.com/QortiumDev/qortium-home/releases',
  coreChangelog: 'https://github.com/QortiumDev/qortium-core/blob/main/QORTIUM-CHANGELOG.md',
  coreDocs: 'https://github.com/QortiumDev/qortium-core/tree/main/docs',
  qortalSite: 'https://qortal.org',
  qortalHub: 'https://github.com/Qortal/Qortal-Hub',
} as const;

/**
 * Release facts. The current version is NOT hardcoded — it is fetched at build
 * time from GitHub via `fetchLatestTag(repoSlug)` (src/lib/releases.ts) and
 * hidden if GitHub is unreachable. `repoSlug` is the owner/name used for that.
 */
export const RELEASES = {
  core: {
    name: 'Qortium Core',
    repoSlug: 'QortiumDev/qortium-core',
    license: 'GPL-3.0',
    repo: LINKS.coreRepo,
    releases: LINKS.coreReleases,
    asset: 'qortium-preview.zip',
    platforms: ['Linux', 'macOS', 'Windows', 'Docker'],
  },
  home: {
    name: 'Qortium Home',
    repoSlug: 'QortiumDev/qortium-home',
    license: '0BSD',
    repo: LINKS.homeRepo,
    releases: LINKS.homeReleases,
    platforms: [
      'Linux AppImage (x64 / arm64)',
      'macOS DMG',
      'Windows portable',
      'Android APK',
    ],
  },
} as const;

/** Previewnet facts. */
export const PREVIEWNET = {
  localApiPort: 24891,
  publishName: 'QortiumHomeTest',
} as const;
