# Verification record

Current version: 0.7.0. This record distinguishes implemented behavior from completed browser checks. Full 1:1 parity is not claimed.

| Area | Implemented | Evidence / remaining limits |
| --- | --- | --- |
| Original asset integrity | Yes | Manifest/hash tests; captured JS unmodified |
| Cashlarp branding | Yes | Login and account checked; icon checked on dark/checker backgrounds; full wordmark fits, light/dark variants |
| Native local signup/login | Yes | Original captured forms; fresh installations contain zero accounts. Email/SMS signup, repeat login, interrupted signup and contact-edit isolation covered by HTTP tests; browser CI passed signup, sign-out and returning login against the actual bundles. |
| Money, payments, requests | Yes | Native funding/payment browser checks; atomic/idempotency and request authorization tests |
| Savings summary | Yes | Native Activity shows Cash and Savings. Original deposit/withdraw forms passed browser QA, with balances checked after reload. Atomic conservation, concurrent retries, overdrafts, account isolation and PIN replay are covered by tests. Savings history uses its own balance perspective; goals, Round Ups and interest remain pending. |
| Activity, filters and CSV | Yes | Native filtered export and owner isolation tested; pagination is one local result set |
| Bitcoin | Yes | Native buy/sell checked; fixed quote and atomic balances tested; no live market |
| Card activation/lock/PIN | Yes | Native activation, wrong PIN, unlock and persistent PIN changes checked |
| Card drawing | Yes | Native White card, drawn K, Undo/redraw, save and reload checked |
| Card stamps | Yes | 245 original stamps plus the monochrome Netanyahu stamp; football selected, saved and reloaded in original card renderer |
| Card styles | Yes | Ten original configurations plus Cashlarp; picker checked, Chameleon Metal selected and persisted; Cashlarp green artwork checked in the native 3D preview and 2D drawing editor; every style's editor is not individually checked |
| Adaptive Card Studio rendering | Yes | Original 2D fallback checked in managed browser; capable-device 3D path requires further device testing |
| Name/cashtag/contact/address | Yes | Original forms checked; aliases restricted to reserved local fixtures |
| PIN requirement | Yes | Server spoof rejection, wrong PIN, replay/exactly-once covered; additional native funding UI checks pending |
| Notifications | Yes | Native categories render; exhaustive channel toggle/reload checks pending |
| Appearance | Yes | Native Dark persists after reload; Light/Dark logos readable |
| Documents | Partial | Native empty collections; local CSV available, statements not generated |
| Public profile link | Partial | Link routes to Pay & Request; recipient preselection and public visibility enforcement pending |
| Replacement card journey | Pending | Original button present; report-lost scenario adapter not yet implemented |
| Bank linking / replacement | Pending | Simulated default source; native link/remove/replace adapters pending |
| Profile photo | Yes | Original upload dialog stores cropped JPEG/PNG in SQLite; save/reload passed against the native browser dialog; removal and MIME handling covered by regression tests |
| Personal-data download | Pending | Link present; full export endpoint pending |
| Account closure | Pending | Original entry present; local recoverable closure adapter pending |
| Passkeys | Partial | Empty native credential list; actual WebAuthn enrollment/login not implemented |
| Taxes / investing / real banking | Not implemented | Local simulation only; no external money, bank, tax or brokerage service |

All custom HTML pages have been deleted. Boot documents adapt the captured login document in memory; only the account mount id, entrypoints, session globals and local transport differ. No hand-authored forms or page layouts are inserted. Legacy console/About routes redirect to native login. Test identities exist only in `tests/fixtures.py` and are never created by production startup.

The default server listens on loopback. Development preview may bind 0.0.0.0 inside the managed QA environment. No public deployment was made.
