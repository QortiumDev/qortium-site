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
  { label: 'Apps', href: '/apps' },
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
  siteRepo: 'https://github.com/QortiumDev/qortium-site',
  qortalSite: 'https://qortal.org',
  qortalHub: 'https://github.com/Qortal/Qortal-Hub',
} as const;

/**
 * Maintainer support rails shown on /support. Only rails that actually accept
 * money today belong here — a listed-but-dead destination is worse than an
 * absent one. That page is also the business URL on file with the card
 * processor, so its billing / refund / contact / privacy copy is load-bearing.
 * Keep it accurate.
 */
export const SUPPORT = {
  kofi: 'https://ko-fi.com/quickmythril',
  liberapay: 'https://liberapay.com/QuickMythril',
  email: 'quickmythril@protonmail.com',
  pageUrl: absUrl('/support'),
  /**
   * Stripe Payment Links. Unlike PayPal's dashboard share links (documented as
   * valid ~6 months), these do not expire. Each returns to the support page on
   * completion. Supporters manage or cancel a monthly plan from the link in
   * their receipt email (Stripe's customer portal) — the billing copy below
   * promises that, so do not remove the portal without changing the copy.
   */
  /**
   * Stripe's no-code customer portal login link. Supporters enter their email,
   * Stripe mails them a session link, and they can cancel or update from there.
   * This is NOT automatic: receipt emails contain no portal link (verified by
   * reading a live receipt on 2026-07-28), so the cancellation promise in the
   * billing copy depends on this link staying on the page.
   */
  portal: 'https://billing.stripe.com/p/login/00wbJ16AYabxfZed2D3Nm00',
  card: {
    monthly3: 'https://buy.stripe.com/00wbJ16AYabxfZed2D3Nm00',
    monthly8: 'https://buy.stripe.com/14A14n8J6erN28ogeP3Nm01',
    monthly20: 'https://buy.stripe.com/7sYcN58J63N95kA4w73Nm02',
    oneTime: 'https://donate.stripe.com/4gM6oH8J66ZlaEU9Qr3Nm03',
  },
} as const;

/**
 * Direct crypto support shown on /support. IMPORTANT: Qortium Previewnet has no
 * native coin, so the QORT addresses below live on the QORTAL MAINNET chain —
 * the page copy must keep saying so explicitly. Crypto goes straight to the
 * listed recipient's own chain address (7R15's goes to him, not through
 * QuickMythril), it is irreversible, and it is NOT covered by the Stripe /
 * Ko-fi / Liberapay billing + refund copy, which stays scoped to those rails.
 */
export const CRYPTO = {
  quickmythril: {
    /** QORT address on the Qortal mainnet chain. */
    qortAddress: 'QT4zHex8JEULmBhYmKd5UhpiNA46T5wUko',
    /** QuickMythril's QDN site — more coins are listed there. */
    qdnSiteGateway: 'https://qdn.qortium.app/WEBSITE/QuickMythril/qm-site',
    qdnSiteResource: 'qdn://WEBSITE/QuickMythril/qm-site',
  },
  tris: {
    /** Registered Qortal name. Address verified against the Qortal mainnet
     *  name registry on 2026-07-29 (name 7R15M3G157U5 owns it). */
    name: '7R15M3G157U5',
    /** QORT address on the Qortal mainnet chain. */
    qortAddress: 'QTqnNyDrUSdeH8QhwXqB6bxoGtLUjCvd4R',
    /** His Donation app, live on Qortium Previewnet QDN. */
    donationAppGateway: 'https://qdn.qortium.app/APP/7R15M3G157U5/Donation',
    donationAppResource: 'qdn://APP/7R15M3G157U5/Donation',
  },
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

/**
 * QDN Q-Apps shown on /apps, listed alphabetically by name. `mark` is the
 * AppMark registry key used to render each card's icon (Chat and Trust use
 * the dedicated ChatMark / TrustMark components instead).
 */
export const APPS: {
  name: string;
  mark: string;
  description: string;
  qdnResource: string;
  page?: string;
}[] = [
  {
    name: 'Apps',
    mark: 'apps',
    description: 'Qortium app browser and launcher.',
    qdnResource: 'qdn://APP/Apps/Apps',
  },
  {
    name: 'Chain',
    mark: 'chain',
    description: 'Block explorer and transaction viewer.',
    qdnResource: 'qdn://APP/Chain/Chain',
  },
  {
    name: 'Chat',
    mark: 'chat',
    description: 'QDN chat app — one-to-one messages and group rooms.',
    qdnResource: CHAT.qdnResource,
    page: '/chat',
  },
  {
    name: 'Groups',
    mark: 'groups',
    description: 'Group discovery and management.',
    qdnResource: 'qdn://APP/Groups/Groups',
  },
  {
    name: 'Help',
    mark: 'help',
    description:
      'Help and feedback app for issues, ideas, replies, edits, completion status, and shareable links.',
    qdnResource: 'qdn://APP/Help/Help',
  },
  {
    name: 'Library',
    mark: 'library',
    description: 'QDN document reader and library.',
    qdnResource: 'qdn://APP/Library/Library',
  },
  {
    name: 'Minting',
    mark: 'minting',
    description: 'Shows node minting state and recent signers.',
    qdnResource: 'qdn://APP/Minting/Minting',
  },
  {
    name: 'Names',
    mark: 'names',
    description: 'Name registration and marketplace.',
    qdnResource: 'qdn://APP/Names/Names',
  },
  {
    name: 'Network',
    mark: 'network',
    description: 'Network topology viewer, including I2P connections.',
    qdnResource: 'qdn://APP/Network/Network',
  },
  {
    name: 'Node',
    mark: 'node',
    description:
      'Inspect a running Core node — status, peers, diagnostics, and bounded settings edits.',
    qdnResource: 'qdn://APP/Node/Node',
  },
  {
    name: 'Profile',
    mark: 'profile',
    description: 'Account profiles and stats.',
    qdnResource: 'qdn://APP/Profile/Profile',
  },
  {
    name: 'Publish',
    mark: 'publish',
    description: 'QDN resource following, blocking, and publishing.',
    qdnResource: 'qdn://APP/Publish/Publish',
  },
  {
    name: 'Trust',
    mark: 'trust',
    description:
      'Explore the on-chain trust network and rate accounts in Home; read-only in a plain browser.',
    qdnResource: TRUST.qdnResource,
    page: '/trust',
  },
  {
    name: 'Wallet',
    mark: 'wallet',
    description: 'Multi-coin crypto wallet — send and receive, history, and address book.',
    qdnResource: 'qdn://APP/Wallet/Wallet',
  },
];

/** Previewnet facts. */
export const PREVIEWNET = {
  localApiPort: 24891,
  publishName: 'QortiumHomeTest',
} as const;
