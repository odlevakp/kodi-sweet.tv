# Sweet.TV Kodi Addon

## Project Overview

Kodi PVR/IPTV addon for sweet.tv streaming service. Integrates with IPTV Manager to provide native TV experience in Kodi (channels in TV section, EPG grid, etc.).

## Architecture

- **Addon type**: `xbmc.python.pluginsource` video addon with IPTV Manager integration
- **Target**: Kodi 21 (Omega) and latest, Python 3.x only
- **EPG delivery**: Via IPTV Manager -> PVR IPTV Simple Client for native TV section
- **Auth**: Device pairing (no username/password) - user enters code at sweet.tv website
- **Streams**: HLS via inputstream.adaptive

## Key Files

- `addon.py` - Entry point and URL router
- `resources/lib/sweettv_api.py` - API client (auth, channels, EPG, streams, movies)
- `resources/lib/iptv_manager.py` - IPTV Manager integration
- `resources/lib/plugin.py` - Main plugin logic and navigation
- `resources/settings.xml` - Addon settings definition

## API Reference

- Base URL: `https://api.sweet.tv/` (all POST, JSON body)
- Billing URL: `https://billing.sweet.tv/`
- Auth: Bearer token from device pairing flow
- Required headers: User-Agent (Chrome), Origin/Referer (sweet.tv), x-device (1;22;0;2;3.7.1)
- Reference implementation: `tmp/archivczsk-doplnky/plugin_video_sweettv/`

## Development Notes

- Use `tmp/` directory for temporary cloning or resource downloads
- Commit and push progress incrementally
- English UI first, Slovak localization planned
- Adult content filtered by category ID 1 in channel data
