# Qortium site

The public website for Qortium. It explains the current Core, Home, Chat, Trust,
and app ecosystem, compares Qortium's goals with Qortal's, and links to releases
and QDN resources. The production site is <https://qortium.app>.

The site is built with Astro and MDX as static HTML. It is served both from the
VPS web roots behind `qortium.app` and as `qdn://WEBSITE/Qortium/Qortium`.

## Pages and app catalog

Current routes are:

- `/` — overview
- `/compare` — Qortium and Qortal goals and tradeoffs
- `/core`, `/home`, `/chat`, and `/trust` — component and app overviews
- `/apps` — the current QDN app catalog
- `/downloads` — Core and Home downloads

The app catalog currently lists Apps, Chain, Chat, Groups, Help, Library,
Minting, Names, Network, Node, Profile, Publish, Trust, and Wallet. Navigation,
links, release metadata, and that catalog live in `src/data/site.ts`.

When rendered inside Qortium Home, QDN references use the `qdnRequest` bridge's
`OPEN_NEW_TAB` action. In a plain browser or public gateway, the same references
remain copyable and external web links open normally.

## QAVS and display settings

The site is at QAVS `1.4.0`: the `1.4` portion is its minimum Qortium platform
level and the patch number tracks this site release. Astro's
`qortium-app-manifest` build hook reads `package.json` and emits
`dist/qortium-app.json` with the name `Qortium` and the current version.

The rendered site follows Home theme, accent, and text-size settings. It has its
own website layout and does not implement the QDN app Classic, Modern, or Fun UI
style modes.

## Develop and build

```sh
npm install
npm run dev       # Astro dev server at http://localhost:4321/
npm run check     # Astro and TypeScript diagnostics
npm run build     # static output in dist/
npm run preview   # preview dist/
```

`astro.config.mjs` deliberately has no base prefix. It uses relative assets and
`format: 'file'`, producing flat files such as `compare.html`; `withBase()` in
`src/data/site.ts` creates matching relative links for both QDN and ordinary
static hosting.

## Publish and deploy

Direct package scripts are available for each normal target:

```sh
npm run qdn:publish:build  # build, then publish previewnet WEBSITE/Qortium/Qortium
npm run qdn:publish        # publish the existing dist/
npm run site:deploy:build  # build, then deploy to both VPS web seeds
npm run site:deploy        # deploy the existing dist/
```

The QDN publisher defaults to the local Previewnet Core at
`http://127.0.0.1:24891` and the account file at
`~/qortium/git/qortium-core/preview/secrets/initial-minting-accounts.json`.
Environment overrides use the `QORTIUM_SITE_` prefix. The identified render URL
is `http://127.0.0.1:24891/render/WEBSITE/Qortium/Qortium`.

`scripts/release-site.sh` provides unified release targets:

```sh
npm run release:preview                         # previewnet QDN
npm run release:vps                             # qortium.app VPS seeds
bash scripts/release-site.sh --mainnet           # Qortal mainnet QDN
npm run release:all                             # previewnet, mainnet, and VPS
bash scripts/release-site.sh --previewnet --vps # combined subset
```

Mainnet publishing is intentionally user-run. It broadcasts a real Qortal
transaction, requires a wallet and password file through `--wallet` /
`QORTAL_WALLET` and `--password-file` / `QORTAL_PASSWORD_FILE`, and asks for
confirmation unless `--yes` is supplied. Use `--dry-run` to inspect a release
sequence without building, publishing, or deploying.
