# Sweet.TV Kodi Addon

A Kodi addon for [sweet.tv](https://sweet.tv) streaming service that provides a native TV experience with live channels, EPG guide, archive/catchup, and VOD content.

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
- [IPTV Manager](https://github.com/add-ons/service.iptv.manager) addon
- [PVR IPTV Simple Client](https://github.com/kodi-pvr/pvr.iptvsimple) addon
- Active sweet.tv subscription

## Installation

1. Install IPTV Manager and PVR IPTV Simple Client from the Kodi addon repository
2. Install this addon (manual ZIP or from repository)
3. Open the addon settings and select "Pair Device"
4. Follow the on-screen instructions to pair your device at sweet.tv
5. Channels will appear in Kodi's TV section automatically

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
sweet.tv API <-> sweettv_api.py <-> plugin.py <-> IPTV Manager <-> PVR IPTV Simple Client <-> Kodi TV Section
```

- HLS streams are played via `inputstream.adaptive`
- EPG data is provided as XMLTV format through IPTV Manager
- Channel list is provided as M3U format through IPTV Manager

## Development

Based on the [Enigma2 sweet.tv plugin](https://github.com/archivczsk/archivczsk-doplnky/tree/main/plugin_video_sweettv) for API reference.

## License

GPL-3.0
