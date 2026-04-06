# Sweet.TV Kodi Addon

A Kodi addon for [sweet.tv](https://sweet.tv) streaming service that provides a native TV experience with live channels, EPG guide, archive/catchup, and VOD content.

> [!NOTE]
> This addon was vibe-coded with Claude Code. It works, but expect rough edges.
> Bug reports and PRs are welcome!

## Features

- **Live TV** - Watch sweet.tv channels directly in Kodi's TV section
- **EPG Guide** - Full electronic program guide integrated with Kodi's TV guide
- **Archive/Catchup** - Watch previously aired programs (per-channel availability)
- **VOD/Movies** - Browse movies by genre and collection
- **Search** - Search across movies and EPG records
- **Stream Quality** - Configurable maximum bitrate
- **Adult Content Filter** - Toggle adult channel visibility
- **Device Management** - View and remove registered devices

## Requirements

- Kodi 21 (Omega) or later
- Active sweet.tv subscription
- The following addons (must be installed manually from Kodi's official repo):
  - **IPTV Manager** (`service.iptv.manager`) — bridges addon data to PVR
  - **PVR IPTV Simple Client** (`pvr.iptvsimple`) — provides native TV section

## Installation

### Step 1: Install Dependencies

In Kodi:

1. **Add-ons → Search** (magnifying glass icon) → search for **"IPTV Manager"** → Install
2. **Add-ons → My add-ons → PVR clients → PVR IPTV Simple Client** → Enable (it's bundled with Kodi)

### Step 2: Install Sweet.TV Addon

1. Download `plugin.video.sweettv-YYYY.MM.DD.N.zip` from the [latest release](https://github.com/odlevakp/kodi-sweet.tv/releases/latest)
2. In Kodi: **Settings → Add-ons → Install from ZIP file** → select the ZIP
3. Open the addon: **Add-ons → Video add-ons → Sweet.TV**

### Step 3: Pair Your Device

1. In the Sweet.TV addon settings, click **Pair Device**
2. The addon shows a pairing code
3. On your computer or phone, go to [sweet.tv](https://sweet.tv) and log in
4. Navigate to your profile → **My Devices**
5. Enter the pairing code and click **Activate**
6. The addon will detect the pairing automatically

### Step 4: Configure IPTV Manager + PVR Simple Client

This step makes channels appear in Kodi's native **TV** section.

1. **Add-ons → My add-ons → Services → IPTV Manager → Configure**
2. Under **IPTV Simple** category, click **"Configure IPTV Simple automatically"**
3. Under **Sources** category, click **"Force refresh now"**
4. Wait until it stops spinning — IPTV Manager fetches channels and EPG from Sweet.TV
5. **Restart Kodi**

After restart, channels will appear under the **TV** menu with full EPG support.

#### If channels still don't appear

The auto-configure may not work on all Kodi installations. Configure manually:

1. **Add-ons → My add-ons → PVR clients → PVR IPTV Simple Client → Configure**
2. **General** tab:
   - Location: **Local Path**
   - M3U Play List Path: `special://userdata/addon_data/service.iptv.manager/playlist.m3u8`
3. **EPG Settings** tab:
   - Location: **Local Path**
   - XMLTV Path: `special://userdata/addon_data/service.iptv.manager/epg.xml`
4. Restart Kodi.

## Usage

### Browse Channels (Addon UI)

**Add-ons → Video add-ons → Sweet.TV → Live TV** — browse by category, mark favourites with the context menu.

### Watch in TV Section

After completing Step 4 above, channels appear in Kodi's main **TV** menu with:
- Live channel guide
- EPG (current + upcoming programs)
- Catchup playback for supported channels

### Favourites

While browsing channels in the addon UI, open the context menu on any channel and select **Add to Favourites**. A **Favourites** category appears at the top of the Live TV list. Favourites are stored locally per Kodi install.

### Archive / Catchup

**Add-ons → Video add-ons → Sweet.TV → Archive** — pick a channel, then a day, then a program.

## Device Pairing

Sweet.tv uses device pairing instead of username/password login:

1. The addon generates a pairing code
2. Go to [sweet.tv](https://sweet.tv) on your computer or phone
3. Log in to your account
4. Navigate to your profile -> "My Devices"
5. Enter the pairing code and click "Activate"
6. The addon will automatically detect the pairing and start working

## Settings

| Setting              | Description                        | Default   |
|----------------------|------------------------------------|-----------|
| Max Bitrate          | Maximum stream bandwidth            | Unlimited |
| Show Adult Channels  | Toggle adult content visibility     | Off       |
| EPG Days             | Number of days to load EPG data     | 3         |
| Stream Close on Stop | Auto-close stream on playback stop  | On        |

## Architecture

This addon integrates with Kodi's native TV functionality through IPTV Manager:

```
sweet.tv API
    ↕
sweettv_api.py
    ↕
addon.py
    ↕
IPTV Manager
    ↕
PVR IPTV Simple Client
    ↕
Kodi TV Section
```

- HLS streams are played via `inputstream.adaptive`
- EPG data is provided as XMLTV format through IPTV Manager
- Channel list is provided as M3U format through IPTV Manager

## Auto-Update Repository

This addon includes a Kodi repository for automatic updates:

1. Download `repository.sweettv-1.0.0.zip` from the [latest release](https://github.com/odlevakp/kodi-sweet.tv/releases/latest)
2. Install it in Kodi via Settings -> Add-ons -> Install from ZIP file
3. Install Sweet.TV from the repository
4. Future updates will be picked up automatically by Kodi

## Development

Based on the [Enigma2 sweet.tv plugin](https://github.com/archivczsk/archivczsk-doplnky/tree/main/plugin_video_sweettv) for API reference.

### Documentation

- [Architecture](docs/architecture.md) — how the addon, IPTV Manager, and PVR Simple Client fit together
- [API Reference](docs/api-reference.md) — sweet.tv API endpoints, auth flow, and gotchas
- [Localization](docs/localization.md) — how strings, translations, and the `M.NAME` constants work
- [Debugging](docs/debugging.md) — log locations, common issues, and recovery steps

### Prerequisites

- GNU sed (`brew install coreutils` on macOS for `gsed`)
- GitHub CLI (`gh`) for releases

### Make Commands

| Command          | Description                                                      |
|------------------|------------------------------------------------------------------|
| `make build`     | Build installable addon ZIP in `dist/`                           |
| `make repo`      | Build repository addon ZIP in `dist/`                            |
| `make repo-index`| Regenerate `repo/addons.xml` and `repo/addons.xml.md5`          |
| `make release`   | Build, update repo index, tag, push, and create GitHub release   |
| `make version`   | Print current version (today's date: YYYY.MM.DD)                 |
| `make clean`     | Remove `dist/` build artifacts                                   |

### Versioning

Releases use date-based versions: `2026.04.05`, `2026.04.06`, etc.

## License

GPL-3.0
