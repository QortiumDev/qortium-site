/* ============================================================================
   Qortium site — shared data + helpers (single source of truth)
   Every page/component imports from here. Do not hardcode nav, URLs, or repo
   links in pages.
   ========================================================================== */

/**
 * Build a RELATIVE in-page link/asset path. The site is published to QDN and
 * shown through the Core render endpoint, which injects a <base href> at the
 * resource root and resolves only relative paths — a root-absolute "/foo" would
 * escape the resource. The build emits flat files (compare.html, core.html, …)
 * so every page is at the resource root and these resolve the same from any page.
 *   withBase('/')            -> "./"
 *   withBase('/compare')     -> "./compare.html"
 *   withBase('/favicon.svg') -> "./favicon.svg"
 * For absolute canonical/OG/JSON-LD URLs use absUrl() instead.
 */
export function withBase(path = '/'): string {
  if (!path || path === '/') return './';
  let p = path.startsWith('/') ? path.slice(1) : path;
  p = p.replace(/\/+$/, '');
  // A route (no file extension) maps to a flat .html file; assets are left as-is.
  const lastSeg = p.split('/').pop() ?? '';
  if (!lastSeg.includes('.')) p += '.html';
  return './' + p;
}

export const SITE = {
  name: 'Qortium',
  tagline: 'A complete internet platform, built by the community',
  description:
    'Qortium is a complete internet platform for the everyday things you go online to do — sharing posts and media, messaging, publishing pages and apps, and storing files. It is built by the community and not controlled by any company, so no one can shut people out and you decide what you see.',
  /**
   * Canonical origin for absolute meta URLs (canonical/OG/JSON-LD/sitemap). The
   * site is multi-homed — Qortal QDN (Qortium/default, gateway path /Qortium),
   * Qortium QDN (Qortium/Qortium), and this brand domain — so we declare ONE
   * stable canonical home here regardless of which copy is being served.
   */
  origin: 'https://qortium.app',
  ogImage: '/og-default.png',
} as const;

/**
 * Absolute URL for canonical / Open Graph / JSON-LD meta tags only. In-page
 * links/assets use the relative withBase() instead. Routes map to the flat
 * .html file actually emitted (build format 'file'), so the canonical resolves
 * on a plain static host and on QDN alike; assets (with an extension) are left
 * as-is.
 *   absUrl('/')               -> "https://qortium.app/"
 *   absUrl('/compare')        -> "https://qortium.app/compare.html"
 *   absUrl('/og-default.png') -> "https://qortium.app/og-default.png"
 */
export function absUrl(path = '/'): string {
  if (!path || path === '/') return SITE.origin + '/';
  let p = path.startsWith('/') ? path.slice(1) : path;
  p = p.replace(/\/+$/, '');
  const lastSeg = p.split('/').pop() ?? '';
  if (!lastSeg.includes('.')) p += '.html';
  return SITE.origin + '/' + p;
}

/**
 * Accent colors offered by the in-page color picker. Ids match Qortium Home's
 * accent option ids, and the swatch hexes mirror Home's light-theme accent
 * values (same values used in global.css for :root[data-accent="…"]), so a
 * standalone/gateway visitor's choice lines up with the embedded experience.
 */
export const ACCENTS: { id: string; label: string; hex: string }[] = [
  { id: 'green', label: 'Green', hex: '#21824a' },
  { id: 'blue', label: 'Blue', hex: '#2a79f3' },
  { id: 'orange', label: 'Orange', hex: '#de8b23' },
  { id: 'purple', label: 'Purple', hex: '#7b44da' },
  { id: 'red', label: 'Red', hex: '#d53e3e' },
  { id: 'teal', label: 'Teal', hex: '#17a398' },
  { id: 'cyan', label: 'Cyan', hex: '#1298d8' },
  { id: 'pink', label: 'Pink', hex: '#d43f86' },
  { id: 'yellow', label: 'Yellow', hex: '#d6a828' },
];

/** Primary navigation (label + internal path). */
export const NAV: { label: string; href: string }[] = [
  { label: 'Compare', href: '/compare' },
  { label: 'Core', href: '/core' },
  { label: 'Home', href: '/home' },
  { label: 'Chat', href: '/chat' },
  { label: 'Trust', href: '/trust' },
  { label: 'Downloads', href: '/downloads' },
];

/** External repositories / sources. Keep these as the only place URLs live. */
export const LINKS = {
  coreRepo: 'https://github.com/QortiumDev/qortium-core',
  homeRepo: 'https://github.com/QortiumDev/qortium-home',
  coreReleases: 'https://github.com/QortiumDev/qortium-core/releases',
  homeReleases: 'https://github.com/QortiumDev/qortium-home/releases',
  coreChangelog: 'https://github.com/QortiumDev/qortium-core/blob/main/QORTIUM-CHANGELOG.md',
  coreDocs: 'https://github.com/QortiumDev/qortium-core/tree/main/docs',
  coreChatEncryptionDoc:
    'https://github.com/QortiumDev/qortium-core/blob/main/docs/chat/private-group-chat-encryption.md',
  coreTrustDoc:
    'https://github.com/QortiumDev/qortium-core/blob/main/docs/trust/account-trust-network.md',
  coreAuraMintingDoc:
    'https://github.com/QortiumDev/qortium-core/blob/main/docs/trust/aura-trust-tier-minting.md',
  chatRepo: 'https://github.com/QortiumDev/qortium-chat',
  trustRepo: 'https://github.com/QortiumDev/qortium-trust',
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

/**
 * Qortium Chat is a QDN Q-App, NOT a GitHub-release download. It ships via QDN
 * (published as a QDN APP resource), runs inside Qortium Home, and has no release
 * binary/asset/tag to link. So it is deliberately kept OUT of RELEASES: do not
 * give it `releases`/`asset`/`platforms` fields and do NOT use <ReleaseTag> for
 * it. Downloads/Docs should route it to its repo + "open it inside Qortium Home",
 * never to a GitHub releases binary.
 */
export const CHAT = {
  name: 'Qortium Chat',
  repoSlug: 'QortiumDev/qortium-chat',
  repo: LINKS.chatRepo,
  license: '0BSD',
  artifact: 'QDN Q-App',
  qdnResource: 'qdn://APP/Chat/Chat',
  runsInside: 'Qortium Home',
} as const;

/**
 * Qortium Trust — same shape/rules as CHAT: a first-pass QDN Q-App explorer for
 * the on-chain account-trust network (browses trust data; can submit RATE_ACCOUNT
 * ratings via Home, read-only in a plain browser), NOT a GitHub-release download.
 * No <ReleaseTag>, no releases link; route to the repo + "open inside Qortium
 * Home". The substantive subject (the trust network itself) is a Core feature —
 * see LINKS.coreTrustDoc / LINKS.coreAuraMintingDoc.
 */
export const TRUST = {
  name: 'Qortium Trust',
  repoSlug: 'QortiumDev/qortium-trust',
  repo: LINKS.trustRepo,
  license: '0BSD',
  artifact: 'QDN Q-App',
  qdnResource: 'qdn://APP/Trust/Trust',
  runsInside: 'Qortium Home',
} as const;

/** Previewnet facts. */
export const PREVIEWNET = {
  localApiPort: 24891,
  publishName: 'QortiumHomeTest',
} as const;
