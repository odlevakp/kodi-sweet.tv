# Sweet.TV Kodi Addon - Claude Code Project Config

## Project Context

This is a Kodi video addon for sweet.tv streaming service. It provides native TV integration via IPTV Manager + PVR IPTV Simple Client.

## Working Conventions

- **Commit often**: Commit and push as progress is made, not just at the end.
- **Track progress**: Keep `.ai-wp` updated with current phase status.
- **Temp files**: Use `tmp/` directory for cloning repos or downloading resources.
- **WIP in git**: All work-in-progress files (.ai-wp, CLAUDE.md, .claude/) are tracked in git for resumability.

## Code Style

- Python 3.x only (Kodi 21+ target).
- Follow Kodi addon conventions for file structure.
- Comments are sentences ending with a period.
- Empty lines between indented blocks have no trailing spaces.
- English UI strings first, localization support planned (Slovak next).

## Architecture

```
plugin.video.sweettv/
  addon.py          - Entry point, URL router
  service.py        - Background service (stream cleanup, IPTV Manager)
  resources/
    settings.xml    - Addon settings
    lib/
      sweettv_api.py    - API client
      iptv_manager.py   - IPTV Manager integration
```

## API Details

- Base: https://api.sweet.tv/ (all POST, JSON)
- Auth: Device pairing (NOT username/password)
- Streams: HLS via HTTP
- Must close streams via CloseStream to avoid multi-device errors
- Token auto-refresh on code 16 response

## Reference Implementation

Enigma2 plugin cloned to `tmp/archivczsk-doplnky/plugin_video_sweettv/` for API reference.

## Phases

1. **Core Live TV + EPG** - Device pairing, channels, EPG, live playback via IPTV Manager
2. **Archive/Catchup** - Browse and play archived programs
3. **Parental Lock** - Adult content filtering and PIN protection
4. **Subscription Info** - Display plan and subscription details
5. **Additional Features** - VOD, search, device management, quality selection, localization
