# Cashlarp

A local roleplay app using captured Cash App login and account JavaScript with an independent Python/SQLite backend. Balances, transfers, cards and Bitcoin holdings belong to the local simulation. No real financial account, payment rail, card issuer, email or SMS service is connected.

Cashlarp branding replaces the visible wordmarks. The old fixed banner is removed. The logo has a transparent exterior and fully opaque green and white artwork; the wordmark includes room for the final letter and switches to white in native dark mode. The application uses only the captured client screens; the former custom console, About and logo-preview pages have been removed.

## Quick start

Install Python 3.10+ and Git, then:

```sh
git clone https://github.com/yewtubes/cashlarp.git
cd cashlarp
python3 run.py
```

On Windows use `py -3 run.py` or double-click `start.bat`. Linux/macOS users can also run `./start.sh`. No pip packages, npm installation, or frontend rebuild tooling is required. The server adapts the captured boot document in memory; it does not generate replacement HTML pages.

Open **http://127.0.0.1:3000/login**. Use a reserved `@example.com`, `@example.net` or `@example.org` email, or a fictional `+12025550100`–`+12025550199` phone. Verification code: **123456**. New accounts start with $50 million and one fictional BTC. Native signup asks for a name and cashtag.

Fresh installations start with **zero accounts**. There are no pre-created `$kotik` or `$friend` users and no custom sign-in console. Create an account through the captured client's original phone/email → verification → name → cashtag screens; returning users use that same original login. New cards activate with **123456** and start with Cash PIN **1234**. Domain hosting has a separate private access password.

### Docker

With Docker Engine/Desktop and the Compose plugin installed:

```sh
docker compose up -d --build
```

Open the same local URL. Accounts, balances and card art persist in the `cashlarp_data` volume across container updates. Stop with `docker compose down`; avoid `down -v` unless you intend to delete that data. The app runs as a non-root user and publishes port 3000 only on loopback.

### Host on a VPS with HTTPS

Point a domain's DNS A record to your server, allow inbound ports 80 and 443, then run in the cloned repo:

```sh
python3 tools/configure_host.py your-domain.com
docker compose -f compose.yaml -f compose.host.yaml up -d --build
```

Open `https://your-domain.com`. Caddy manages HTTPS certificates and renewals. The browser first asks for the private hosting username/password stored in `.env`; after that, the original roleplay login works normally. Share the hosting password only with the group using this instance. No secret is committed to Git.

The generator creates `.env` once and refuses to replace existing credentials. You can edit that file to change the domain or hosting credentials, then rerun the Compose command. A Python installation is needed only for this optional configuration helper; `.env.example` can also be copied and filled out manually. If the VPS already runs a reverse proxy, use the base Compose file and route your existing HTTPS proxy to `127.0.0.1:3000`; set the access password and `CASHLARP_SECURE_COOKIES=1` in the app environment.

See [Hosting and backups](docs/HOSTING.md) for updates, backup/restore, configuration and troubleshooting. The app needs one persistent SQLite disk and one app instance; ephemeral/serverless storage will lose accounts on replacement.

## Connected original-client features

- Money balance, Add money, Withdraw, Pay and Request.
- Activity, search, filters, sorting, receipts and per-user CSV exports.
- Card activation, lock/unlock and original Cash PIN controls.
- Original Card Studio: ten captured card themes, drawing, Undo, Clear, Pattern, cashtag and 245 original stamps. Designs and theme selection persist to SQLite and reload in the original card renderer.
- Bitcoin purchases and sales at the fixed $100,000/BTC quote, with integer satoshis and atomic cash/holdings updates.
- Name, cashtag, reserved email/phone aliases, address, request privacy, PIN security and notification preferences.
- Original light/dark/auto appearance, with local HTTP preference-cookie adaptation.

Browser verification includes native signup through name/cashtag, funding and payments, PIN editing, address/contact editing, drawing persistence, a football stamp saved and reloaded, ten-theme picker, Chameleon Metal selection/reload, light/dark branding and appearance persistence. See `AUDIT.md` for verification boundaries.

## Architecture and integrity

Captured JavaScript remains byte-for-byte unchanged and checksummed in `capture/manifest.json`. Original account screens, forms, card editor, graphics and dialogs render from those bundles. Both boot documents derive directly from `capture/login.html`, retaining the captured body, styles and loading artwork. The account entrypoint uses its required mount id and session globals. No signed-in account HTML was captured, and no replacement page forms or layouts are generated.

`server.py` owns SQLite state and local HTTP sessions. `compat.py`, `settings_compat.py` and `native_auth.py` implement the original client's contracts. Separate runtime bridges adapt transport, branding, local preferences and Card Studio's existing 2D fallback when WebGL cannot initialize. The original 3D path stays available on capable browsers.

Sessions use hashed tokens, HttpOnly/SameSite cookies and CSRF validation. Passwords/PINs are hashed with scrypt. Financial mutations are atomic and idempotent. Flow tokens and saved card images are scoped to their local owner. Browser CSP restricts connections and forms to the local origin. Unknown native routes fail locally; they never proxy to Cash App. Runtime databases, sessions and browser screenshots are excluded from distributable archives.

## Validation

```sh
python3 -m unittest discover -s tests -v
```

The Python suite and browser CI cover fresh installs with zero accounts, removal of custom HTML pages, native signup/login, interrupted onboarding, original account navigation and logout. The test suite also covers capture hashes, boot wiring, native authentication, session/CSRF isolation, payment/request permissions, overdraft and concurrent retries, ledger conservation, local funding, Bitcoin, card design persistence, export scoping, PIN gating and settings. Browser QA complements these tests; this project is not yet verified as complete 1:1 coverage of every original journey.

## Capture provenance

Capture date: 2026-10-25. Revision: `d964d4f8766900778d7282f4b26521146f6d2785`.

- Login main: `main.1973b48deea66eb9.js`.
- Account main: `main.fa6baaec96a82623.js`.
- Account runtime: `runtime.a1ea354b43d18d7c.js`; all 79 named lazy chunks captured.
- Public JSON configs: original stamp catalog and ten card-theme definitions.

No real account details or private API responses were imported. Captured anonymous login tokens are sanitized. Original assets belong to their respective owners. This project is unaffiliated with Cash App or Block.
