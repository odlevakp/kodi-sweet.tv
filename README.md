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

Dependencies (auto-installed when you install the addon):
- [IPTV Manager](https://github.com/add-ons/service.iptv.manager) - bridges addon data to PVR
- [PVR IPTV Simple Client](https://github.com/kodi-pvr/pvr.iptvsimple) - provides native TV section
- [inputstream.adaptive](https://github.com/xbmc/inputstream.adaptive) - HLS stream playback

## Installation

1. Download `plugin.video.sweettv-YYYY.MM.DD.zip` from the [latest release](https://github.com/odlevakp/kodi-sweet.tv/releases/latest)
2. In Kodi, go to **Settings -> Add-ons -> Install from ZIP file**
3. Select the downloaded ZIP — dependencies are installed automatically
4. Open the addon from **Add-ons -> Video add-ons -> Sweet.TV**
5. Go to addon settings and click **Pair Device**
6. Follow the on-screen instructions to pair at sweet.tv
7. **Restart Kodi** — channels will appear in the **TV** section

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
