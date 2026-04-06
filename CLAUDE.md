# Sweet.TV Kodi Addon - Project Context for Claude

This file gives Claude (and humans dropping in) the context needed to work productively on this addon.

## What This Is

A Kodi addon for the [sweet.tv](https://sweet.tv) streaming service. Provides:

- Live TV channels with categories and EPG
- Catchup / archive playback (per-channel)
- Free (AVOD) movies served as channel catchups
- Search across movies and EPG
- Native integration with Kodi's TV section via IPTV Manager + PVR IPTV Simple Client (optional but recommended)

Target: Kodi 21 (Omega) and later, Python 3.x only.

## Where Things Live

- **Implementation**: [plugin.video.sweettv/](plugin.video.sweettv/)
- **Documentation**: [docs/](docs/)
  - [architecture.md](docs/architecture.md) - module structure, data flow, IPTV Manager handshake, stream lifecycle
  - [api-reference.md](docs/api-reference.md) - all sweet.tv API endpoints we use, headers, gotchas
  - [localization.md](docs/localization.md) - how the M.NAME constants and .po files work
  - [debugging.md](docs/debugging.md) - log paths, common issues, recovery without nuking Kodi
- **Progress / status**: [.ai-wp](.ai-wp)
- **Build**: [Makefile](Makefile) (`make build`, `make release`)
- **Reference plugin** (read-only, for API hints): `tmp/archivczsk-doplnky/plugin_video_sweettv/` (gitignored)

When in doubt, **read [docs/architecture.md](docs/architecture.md) first** — it has the data flow diagram and explains how all the pieces fit together.

## Working Conventions

- **Commit per feature**, push incrementally. The user wants visible, granular history.
- **Don't commit/push code changes until the user has confirmed they work** — see [feedback memory](.). Build the ZIP, hand it over, wait for confirmation.
- **Use `gsed` (GNU sed) in Makefiles and scripts**, not BSD sed. It's at `/opt/homebrew/bin/gsed` on the dev mac.
- **Markdown tables in docs should be column-aligned** in plaintext for readability.
- **Comments are sentences ending with a period.** Empty lines between indented blocks have no trailing whitespace.
- **`tmp/` dir is for temporary clones and downloads.** Gitignored.
- **Use `Skill` or built-in tools** instead of bash for file operations. `Read` instead of `cat`, `Edit` instead of `sed`, `Glob`/`Grep` instead of `find`/`grep`.

## Build & Versioning

- Versions are date-based with a counter: `YYYY.MM.DD.N`. The Makefile auto-increments `N` on every `make build`.
- Kodi rejects ZIP installs that match the already-installed version, hence the auto-bump.
- Run `make build` to produce `dist/plugin.video.sweettv-YYYY.MM.DD.N.zip`.
- Run `make release` to also tag, push, and create a GitHub release.

## Technical Decisions

- **IPTV Manager + PVR Simple Client** for the native TV section, not a custom PVR backend.
- **Kodi's built-in HLS player**, NOT inputstream.adaptive — sweet.tv inserts a broken ad preroll from `ads-badtest.sweet.tv` that inputstream.adaptive can't recover from. The built-in player tolerates failed segments and skips past it.
- **Device pairing** (no username/password) — that's how the sweet.tv API works.
- **AVOD movies only** — sweet.tv serves them as channel catchups via `TvService/OpenStream`. Paid movies use Widevine DRM which we don't support.
- **Localized via `M.NAME` constants** in `resources/lib/strings.py`, not bare numeric IDs.
- **English / Slovak / Czech** UI translations.
- **Pinned Channels** (was "Favourites") — renamed because Kodi has built-in Favourites and the two collided in the context menu.

## Key Gotchas (Read These Before Touching)

- **The User-Agent matters.** A Linux Chrome UA causes sweet.tv to route stream URLs through a CDN that returns a media playlist instead of a master playlist. Use Windows Chrome.
- **The `x-device` header matters too.** `1;22;39;2;7.4.50` is needed for movies. `1;22;0;2;3.7.1` worked for live TV but breaks movies. Both endpoints currently work with the new header.
- **Movies aren't VOD.** They're scheduled as catchup events on premium channels. `MovieService/GetLink` is dead — `MovieService/GetMovieInfo` for a single movie returns `channel_id` + `epg_id`, then `TvService/OpenStream` plays it.
- **`GetMovieInfo` bulk vs single is different.** Bulk listings don't include description, duration, or channel_id/epg_id. Only single-movie calls (with `need_extended_info: true`) return those.
- **PVR Simple Client catchup must be enabled** in its own settings before catchup-from-EPG works.
- **Don't ever delete `Addons*.db` in Kodi userdata** — that wipes ALL installed addons, not just ours. Stick to the per-addon paths in [docs/debugging.md](docs/debugging.md).
- **OpenStream URLs are single-use** and expire quickly. Don't cache them.

## Auth Model

Sweet.tv uses **device pairing**, not username/password. Flow:

1. Generate UUID device_id, persist locally.
2. `SigninService/Start.json` with device info → returns `auth_code`.
3. Show code to user. They enter it at sweet.tv → My Devices → Activate.
4. Poll `SigninService/GetStatus.json` until it returns tokens.
5. Use `Authorization: Bearer <access_token>` for everything else.
6. Token expires; refresh via `AuthenticationService/Token.json` with the refresh token.
7. Code 16 in any response means "token expired" — refresh once and retry.

The addon auto-launches the pairing flow if the user opens it without being paired.

## API Cheatsheet

Base URLs:
- `https://api.sweet.tv/` - everything except device management
- `https://billing.sweet.tv/` - device list / remove

All requests are POST with JSON body. Required headers including `x-device` are set up in [`sweettv_api.py`](plugin.video.sweettv/resources/lib/sweettv_api.py). Full endpoint reference: [docs/api-reference.md](docs/api-reference.md).
