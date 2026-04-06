# Sweet.TV Kodi Addon

A Kodi addon for [sweet.tv](https://sweet.tv) streaming service that provides a native TV experience with live channels, EPG guide, archive/catchup, and VOD content.

> [!NOTE]
> This addon was vibe-coded with Claude Code. It works, but expect rough edges.
> Bug reports and PRs are welcome!

## Features

- **Live TV** - Watch sweet.tv channels directly in Kodi's TV section
- **EPG Guide** - Full electronic program guide integrated with Kodi's TV guide
- **Channel Groups** - Sweet.TV categories (Sports, Movies, Kids, etc.) and your pinned channels become PVR channel groups
- **Archive/Catchup** - Watch previously aired programs (per-channel availability, up to 7 days)
- **Free Movies** - Browse free (ad-supported) movies by genre or collection. Paid SVOD/TVOD movies are not supported.
- **Search** - Search across movies and EPG records
- **Pinned Channels** - Pin channels via context menu, stored locally per Kodi install
- **Stream Quality** - Configurable maximum bitrate
- **Adult Content Filter** - Toggle adult channel visibility
- **Device Management** - View and remove registered devices
- **Localization** - English, Slovak, and Czech UI

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

### Step 4: Configure IPTV Manager + PVR Simple Client (optional, recommended)

This step is **optional** — the addon is fully usable from **Add-ons → Video add-ons → Sweet.TV** without it (browse channels, archive, movies, search). But integrating with IPTV Manager + PVR IPTV Simple Client gives you the **full native Kodi TV experience**: channels and EPG in Kodi's TV section, channel groups (sweet.tv categories + your pinned channels), and catchup directly from the TV guide. Strongly recommended if you want this addon to feel like a real TV app.

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

**Add-ons → Video add-ons → Sweet.TV → Live TV** — browse by category, pin channels via the context menu.

### Watch in TV Section

After completing Step 4 above, channels appear in Kodi's main **TV** menu with:
- Live channel guide
- EPG (current + upcoming programs)
- Catchup playback for supported channels

### Pinned Channels

While browsing channels in the addon UI, open the context menu on any channel and select **Pin Channel**. A **Pinned Channels** category appears at the top of the Live TV list. Pinned channels are stored locally per Kodi install.

After the next IPTV Manager refresh, your pinned channels also appear as a **Pinned** channel group in Kodi's native TV section.

### Movies

**Add-ons → Video add-ons → Sweet.TV → Movies** — browse by genre or collection.

Only free (AVOD, ad-supported) movies are listed and playable. Paid movies use Widevine DRM which this addon does not support.

Movie titles show year and IMDB rating in grey: `Title [2019] ★4.9`. For description, duration, and full details, right-click any movie and pick **Sweet.TV details**.

### Archive / Catchup

Two ways to watch past programs:

1. **Addon UI**: **Add-ons → Video add-ons → Sweet.TV → Archive** — pick a channel, then a day, then a program.
2. **TV section (PVR catchup)**: open the **TV Guide**, navigate to a past program on a catchup-enabled channel, press OK, and pick **Play recording**. This requires catchup to be enabled in PVR IPTV Simple Client (see below).

#### Enabling catchup in PVR Simple Client

**Add-ons → My add-ons → PVR clients → PVR IPTV Simple Client → Configure → Catchup**, then set **Enable catchup** to On. Restart Kodi after changing this.

If catchup is enabled but past programs don't play, ensure IPTV Manager has refreshed at least once after upgrading the addon (the EPG file needs the catchup-id attributes which only the new addon writes).

## Main Menu

The addon menu (under **Add-ons → Video add-ons → Sweet.TV**) shows:

| Item                     | What it does                                                       |
|--------------------------|--------------------------------------------------------------------|
| Live TV                  | Browse channels by sweet.tv category, pin channels                 |
| Archive                  | Browse catchup channels and pick a day/program                     |
| Movies                   | Browse free (AVOD) movies by genre or collection                   |
| Search                   | Search across movies and EPG                                       |
| Registered Devices       | List devices linked to your account; current device highlighted   |
| Subscription Information | Show plan, active services with expiry, balance                    |
| Settings                 | Open the addon settings dialog                                     |

If you open the addon and aren't paired yet, the pairing dialog launches automatically.

## Settings

| Setting                   | Description                                            | Default   |
|---------------------------|--------------------------------------------------------|-----------|
| Pair Device               | Run the device pairing flow                            | —         |
| Unpair Device (Logout)    | Clear stored credentials                               | —         |
| Maximum Bitrate           | Cap on stream bandwidth                                | Unlimited |
| API Language              | Language sent to sweet.tv API (Auto / sk / cs / en …)  | Auto      |
| Show Adult Channels       | Toggle adult content visibility                        | Off       |
| EPG Days to Load          | Number of days of EPG data to fetch (1–7)              | 3         |
| Auto-close Stream on Stop | Call CloseStream on playback stop to free the slot     | On        |
| Verbose Logging           | Log API responses and stream details (for debugging)   | Off       |

Each setting shows a longer description in the footer when highlighted.

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

- HLS streams are played via Kodi's built-in HLS player (which tolerates the broken `ads-badtest.sweet.tv` ad preroll that inputstream.adaptive choked on)
- EPG data is provided as XMLTV format through IPTV Manager
- Channel list is provided as M3U format through IPTV Manager
- Movies are streamed as channel catchups, not as standalone VOD — see [docs/architecture.md](docs/architecture.md#movie-playback-avod-only)

For a deeper explanation, read [docs/architecture.md](docs/architecture.md).

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

Releases use date-based versions with a per-day counter: `2026.04.05.0`, `2026.04.05.1`, ..., `2026.04.06.0`. Each `make build` auto-increments the counter so Kodi accepts the install over the previous one.

## License

GPL-3.0
