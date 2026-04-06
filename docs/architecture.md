# Architecture

How the Sweet.TV addon fits together with Kodi, IPTV Manager, and PVR IPTV Simple Client.

## High-Level Picture

```
                                                  ┌──────────────────┐
                                                  │   sweet.tv API   │
                                                  │ api.sweet.tv/... │
                                                  └────────┬─────────┘
                                                           │ HTTPS POST + JSON
                                                           ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          plugin.video.sweettv                              │
│                                                                            │
│   ┌──────────────┐    ┌────────────────┐    ┌──────────────────────────┐  │
│   │  service.py  │    │    addon.py    │    │  resources/lib/          │  │
│   │  (background │◄───┤  URL router    │◄───┤    sweettv_api.py        │  │
│   │   service)   │    │  + UI builder  │    │    iptv_manager.py       │  │
│   └──────┬───────┘    └────────┬───────┘    │    favourites.py         │  │
│          │                     │            │    strings.py            │  │
│          │                     │            └──────────────────────────┘  │
└──────────┼─────────────────────┼────────────────────────────────────────────┘
           │                     │ plugin:// callbacks
           │                     │
           │                     ▼
           │           ┌──────────────────────┐
           │           │  service.iptv.manager│
           │           │   (the Kodi addon)   │
           │           └──────────┬───────────┘
           │                      │ writes M3U + XMLTV files
           │                      ▼
           │           ┌──────────────────────────────────────────────┐
           │           │  ~/.kodi/userdata/addon_data/                │
           │           │      service.iptv.manager/                   │
           │           │          playlist.m3u8                       │
           │           │          epg.xml                             │
           │           └────────────────┬─────────────────────────────┘
           │                            │ reads at startup + on refresh
           │                            ▼
           │                ┌──────────────────────┐
           │                │  pvr.iptvsimple      │
           │                │  (PVR IPTV Simple)   │
           │                └──────────┬───────────┘
           │                           │ exposes channels/EPG via PVR API
           │                           ▼
           │                ┌──────────────────────┐
           │                │   Kodi TV section    │
           │                │   (live + EPG grid)  │
           │                └──────────┬───────────┘
           │                           │ user clicks Play
           │                           │ stream URL = plugin://...play_channel
           ▼                           ▼
   ┌─────────────────────────────────────────────────┐
   │  addon.py play_channel() → sweettv_api → HLS    │
   └─────────────────────────────────────────────────┘
```

The same `addon.py` serves three different consumers:

1. **The user** browsing the addon directly (`Add-ons → Video add-ons → Sweet.TV`).
2. **IPTV Manager** polling for channel and EPG data (via `?action=iptv_channels` / `iptv_epg`).
3. **PVR IPTV Simple Client** invoking `?action=play_channel` when the user clicks a TV channel — the M3U playlist contains `plugin://` URLs as the stream sources, which Kodi resolves by calling our addon.

## File Layout

```
plugin.video.sweettv/
├── addon.xml                         ← Kodi manifest, dependencies
├── addon.py                          ← URL router and all UI handlers
├── service.py                        ← background service (stream cleanup)
├── icon.png                          ← addon icon
└── resources/
    ├── settings.xml                  ← settings UI + IPTV Manager config
    ├── language/
    │   ├── resource.language.en_gb/strings.po
    │   ├── resource.language.sk_sk/strings.po
    │   └── resource.language.cs_cz/strings.po
    └── lib/
        ├── sweettv_api.py            ← all sweet.tv API calls
        ├── iptv_manager.py           ← M3U/XMLTV generation for IPTV Manager
        ├── favourites.py             ← client-side favourite channels
        └── strings.py                ← localization constants (M.PAIR_TITLE etc.)
```

See the [API Reference](api-reference.md) for what `sweettv_api.py` actually calls.

## Module Responsibilities

### addon.py — The Router

When Kodi (or IPTV Manager, or PVR Simple Client) opens any `plugin://plugin.video.sweettv/?...` URL, it spawns `addon.py` as a fresh process. The script reads `sys.argv[2]` (query string), dispatches to a handler based on the `action` parameter, builds a directory listing or resolves a playable URL, and exits.

Each invocation is a new Python process. **Nothing is shared between invocations except the addon's profile directory** (`~/.kodi/userdata/addon_data/plugin.video.sweettv/`), which holds tokens and the favourites file.

Routing roughly:

| Action           | What it does                                              |
|------------------|-----------------------------------------------------------|
| (none)           | Show the main menu                                        |
| browse_channels  | Show channel categories or channels in a category         |
| play_channel     | Resolve and return a live HLS variant URL                 |
| browse_archive   | Show channels with catchup                                |
| archive_day      | Show day picker, then programs for that day               |
| play_catchup     | Resolve archive HLS URL for an EPG event                  |
| browse_movies    | Movie genres / collections                                |
| play_movie       | Resolve movie HLS/DASH URL                                |
| search           | Search both movies and EPG records                        |
| pair_device      | Run the device pairing dialog                             |
| unpair_device    | Logout and clear tokens                                   |
| manage_devices   | List/remove registered devices                            |
| iptv_channels    | IPTV Manager callback — return channel JSON via socket    |
| iptv_epg         | IPTV Manager callback — return EPG JSON via socket        |
| fav_add/fav_remove | Add/remove a channel from local favourites              |

### service.py — Background Service

Started by Kodi at boot via the `xbmc.service` extension point. Runs as a long-lived process. Responsibilities:

- **Stream cleanup**: subscribes to Kodi player events. When a sweet.tv stream stops or ends, calls `CloseStream` on the API to release the slot. Without this, sweet.tv quickly says "watching on too many devices" because each `OpenStream` consumes a stream slot until released.
- **Stream tracking**: when a sweet.tv stream starts, `addon.py` sets a `sweettv_stream_id` property on the ListItem. The service reads it back via `xbmc.Player().getPlayingItem().getProperty(...)` and remembers the ID for cleanup.

The service does NOT make API calls itself (other than CloseStream). It does not poll, refresh, or fetch anything else. It just sits there waiting for player events.

### sweettv_api.py — The API Client

A single class `SweetTVApi` wraps every sweet.tv endpoint we use. Things it handles:

- **Token persistence**: `_load_login_data` / `_save_login_data` read/write `login.json` in the addon profile dir.
- **Token refresh**: before each call, checks `access_token_life < now()`. If expired, calls `AuthenticationService/Token.json` to refresh.
- **Code 16 retry**: if a response includes `code: 16` (token expired between checks), refreshes the token once and retries the same request.
- **Headers**: builds the required `User-Agent`, `Origin`, `Referer`, `x-device`, etc. Two header sets — one for API JSON calls, one for fetching HLS playlists.
- **Stream handling**: `open_stream` returns the master playlist URL and a `stream_id`. `resolve_hls_streams` parses the master playlist for variants (used internally — see [API Reference: Ad Preroll Gotcha](api-reference.md#the-ad-preroll-gotcha)). `close_stream` releases the slot.

This file contains zero Kodi-specific code (other than `xbmc.log`). It could in principle be lifted out and reused.

### iptv_manager.py — M3U/XMLTV Builder

Two top-level functions: `get_channels()` and `get_epg()`. Each builds a JSON dict in IPTV Manager's format and returns it. The actual sending over the socket is done by the `IPTVManager` class.

- `get_channels()` calls `sweettv_api.get_channels()` to get the channel list and categories, then for each available channel builds a stream dict with name, logo, group(s), catchup info. **Groups are computed from sweet.tv categories joined with `;`** so PVR Simple Client creates one channel group per category. The user's local favourites get an additional `Favourites` group prepended.
- `get_epg()` calls `sweettv_api.get_epg_multi_day()` for the configured number of days (default 3) and returns the events keyed by `sweettv-<channel_id>` (matching the channel `id` in `get_channels`).

### favourites.py — Local Favourite Channels

Client-side, JSON-file-backed list of favourite channel IDs stored at `~/.kodi/userdata/addon_data/plugin.video.sweettv/favourites.json`. The sweet.tv API has a "Favorite" category but it's always empty in the channel response — sweet.tv tracks favourites elsewhere (probably their official app's user state, not exposed via this API).

Functions: `load()`, `save()`, `add(id)`, `remove(id)`, `is_favourite(id)`. Used by both `addon.py` (context menu, Favourites category in browse_channels) and `iptv_manager.py` (Favourites channel group).

### strings.py — Localization Constants

Defines `M.PAIR_TITLE`, `M.LIVE_TV` etc. that map to numeric IDs in `.po` files. See [Localization](localization.md) for details.

## The IPTV Manager Handshake

Without the TV section integration, this addon is just a video addon. Channels in the native TV section come via [IPTV Manager](https://github.com/add-ons/service.iptv.manager) version 0.2.x. Here's how that hooks together.

### Discovery

IPTV Manager periodically scans every installed Kodi addon and reads three hidden settings from each addon's `settings.xml`:

```xml
<setting id="iptv.enabled" type="bool" default="true" visible="false"/>
<setting id="iptv.channels_uri" type="text"
         default="plugin://plugin.video.sweettv/?action=iptv_channels&amp;port={port}"
         visible="false"/>
<setting id="iptv.epg_uri" type="text"
         default="plugin://plugin.video.sweettv/?action=iptv_epg&amp;port={port}"
         visible="false"/>
```

If `iptv.enabled` is true, IPTV Manager treats this addon as an integration source.

(Note: IPTV Manager v0.3+ uses an `<iptv_manager>` block in `addon.xml` instead. We use v0.2.x because that's what's in the official Kodi repo.)

### The Refresh Cycle

When the user clicks "Force refresh now" (or every 24h by default), IPTV Manager does this for each integrated addon:

1. Pick a free local TCP port and start listening on `127.0.0.1:<port>`.
2. Read `iptv.channels_uri` from the addon's settings, substitute `{port}` with the actual port, and call `RunPlugin(plugin://...?action=iptv_channels&port=12345)`.
3. Wait for the addon to connect to that port and send a JSON payload, then close the connection.
4. Repeat for `iptv.epg_uri`.
5. Aggregate JSON from all integrated addons into a single `playlist.m3u8` and `epg.xml` written to `~/.kodi/userdata/addon_data/service.iptv.manager/`.
6. Tell PVR IPTV Simple Client to reload (`Addons.SetAddonEnabled` toggle).

### Our Side of the Socket

When `addon.py` is invoked with `?action=iptv_channels&port=12345`, it does:

```python
port = int(params.get("port", [0])[0])
IPTVManager(port).send_channels()
```

`send_channels()` builds the full channel JSON dict via `iptv_manager.get_channels()` and sends it over the socket:

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", port))
sock.sendall(json.dumps(get_channels()).encode())
sock.close()
```

That's the entire "handshake" — IPTV Manager calls us, we serialize JSON, write it to a socket, exit. Same for EPG.

### JSON Format

Channels payload:

```json
{
  "version": 1,
  "streams": [
    {
      "name": "Jednotka HD",
      "stream": "plugin://plugin.video.sweettv/?action=play_channel&channel_id=847",
      "id": "sweettv-847",
      "logo": "http://staticeu.sweet.tv/...png",
      "preset": 1,
      "group": "National;HD channels;Sweet.TV;Favourites",
      "is_catchup": true,
      "catchup_source": "plugin://plugin.video.sweettv/?action=play_catchup&channel_id=847&epg_id={catchup-id}",
      "catchup_days": 7
    }
  ]
}
```

EPG payload:

```json
{
  "version": 1,
  "epg": {
    "sweettv-847": [
      {
        "start": "2026-04-06 18:00:00",
        "stop":  "2026-04-06 19:30:00",
        "title": "News at 7",
        "episode-num": "12345",
        "image": "http://..."
      }
    ]
  }
}
```

The `id` in channels and the keys in `epg` must match for PVR to associate EPG events with channels.

## The PVR Side

PVR IPTV Simple Client has nothing to do with sweet.tv directly. It just reads the `playlist.m3u8` and `epg.xml` files that IPTV Manager wrote, and exposes them to Kodi's PVR system. Channels appear in the **TV** section, the EPG grid populates, and clicking Play resolves the `plugin://plugin.video.sweettv/?action=play_channel&...` URL — which lands back in `addon.py`.

This is the loop. Sweet.TV → API → addon.py → JSON → IPTV Manager → M3U/EPG files → PVR Simple Client → Kodi UI → user clicks → addon.py → API → HLS URL → Kodi player.

### Wiring PVR Simple Client to the IPTV Manager Files

The IPTV Manager has a "Configure IPTV Simple automatically" action that should set this up, but it doesn't always work. If channels still don't show after a refresh, see the [README installation steps](../README.md#step-4-configure-iptv-manager--pvr-simple-client) for the manual paths.

The expected paths are:

- M3U: `special://userdata/addon_data/service.iptv.manager/playlist.m3u8`
- EPG: `special://userdata/addon_data/service.iptv.manager/epg.xml`

Both should be configured as "Local Path" type (not URL).

## Stream Lifecycle in Detail

The most fragile part of the integration. Sweet.TV limits how many streams a single device can open concurrently — if you don't release them, the API starts rejecting `OpenStream` calls with "too many devices".

Step-by-step for a live channel:

1. **User clicks a channel** (either in the addon UI or in the Kodi TV section).
2. Kodi resolves `plugin://plugin.video.sweettv/?action=play_channel&channel_id=847`.
3. `addon.py play_channel()` calls `api.get_live_link(channel_id, max_bitrate=...)`:
   - Internally calls `OpenStream` → returns master playlist URL + `stream_id`.
   - Fetches the master playlist, parses `#EXT-X-STREAM-INF` variants.
   - Picks the best variant within the bitrate limit and returns its URL + the `stream_id`.
4. `addon.py` builds a `xbmcgui.ListItem(path=variant_url)`, sets `MimeType` and a `sweettv_stream_id` property, and calls `setResolvedUrl`.
5. Kodi's built-in HLS player starts playing the variant URL.
6. **`service.py` sees the playback start** via `onAVStarted`, reads `sweettv_stream_id` from the playing item, remembers it.
7. When playback stops (`onPlayBackStopped` / `onPlayBackEnded`), the service calls `api.close_stream(stream_id)`.

If step 7 doesn't run (service crashes, Kodi force-quits, addon disabled), the stream slot stays held until sweet.tv times it out server-side. Eventually you'll hit the device limit and need to either wait or unregister via `manage_devices`.

For PVR-launched playback, the same flow applies — the M3U entry's stream URL is the same `plugin://...play_channel` URL, so `addon.py play_channel` runs, sets the `sweettv_stream_id` property, and `service.py` picks it up. No special handling needed.

### Channel Switching

When the user switches channels in PVR, Kodi closes the current stream (triggering `onPlayBackStopped` → `close_stream`) before starting the next. So channel-switching cleans up automatically.

In the **addon UI** browse mode, switching is just navigating back and clicking a different item — same flow, same cleanup.

### The Ad Preroll

This is the gotcha that broke playback for two days. See [API Reference: Ad Preroll Gotcha](api-reference.md#the-ad-preroll-gotcha). Short version: don't use `inputstream.adaptive` with sweet.tv master playlists; pick a variant URL and let Kodi's built-in HLS player handle it.

## Persistence Locations

| What                    | Where                                                                                |
|-------------------------|--------------------------------------------------------------------------------------|
| Tokens (access/refresh) | `~/.kodi/userdata/addon_data/plugin.video.sweettv/login.json`                        |
| Favourites              | `~/.kodi/userdata/addon_data/plugin.video.sweettv/favourites.json`                   |
| Addon settings          | `~/.kodi/userdata/addon_data/plugin.video.sweettv/settings.xml`                      |
| Generated M3U           | `~/.kodi/userdata/addon_data/service.iptv.manager/playlist.m3u8`                     |
| Generated EPG           | `~/.kodi/userdata/addon_data/service.iptv.manager/epg.xml`                           |
| Kodi log                | `~/.kodi/temp/kodi.log` (or `~/.var/app/tv.kodi.Kodi/data/temp/kodi.log` on Flatpak) |

`~/.kodi` is the standard path. On Flatpak it's under `~/.var/app/tv.kodi.Kodi/data/`. On Android it's somewhere under `/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/`.

Inside the addon Python code, prefer `xbmcvfs.translatePath('special://userdata/...')` instead of hardcoding paths.

## What's Not Cached

- **Channel list and EPG** — fetched fresh from sweet.tv on every `iptv_channels` / `iptv_epg` call. There's no in-memory cache because every plugin invocation is a fresh Python process. Adding a disk cache with TTL would be straightforward but hasn't been needed yet — the channel list call returns in ~500ms.
- **HLS variant URLs** — fetched on every play. They include short-lived tokens.

## What Could Go Wrong (Architecturally)

- **Service crashes after starting playback** → stream slot leaks. Manual fix: `manage_devices` and remove the device, or wait for server-side timeout.
- **IPTV Manager refresh races with PVR Simple reload** → channels temporarily disappear. Self-heals on the next refresh.
- **Stale tokens not refreshed correctly** → user needs to re-pair. The code-16 retry handles most cases, but a refresh-token failure forces a logout.
- **Addon process timeout while fetching EPG** → IPTV Manager gives up waiting on the socket. EPG ends up empty for sweet.tv this cycle. The next refresh tries again.
