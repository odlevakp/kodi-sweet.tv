# Debugging

When something is broken, the answer is almost always in the Kodi log. This document covers where to find logs, what to grep for, how to enable extra debug output, and how to recover from common bad states without nuking your Kodi setup.

## Where Kodi Logs Live

The path depends on how Kodi is installed:

| Install method                 | Log path                                                              |
|--------------------------------|-----------------------------------------------------------------------|
| Standard Linux / macOS / Win   | `~/.kodi/temp/kodi.log`                                               |
| Flatpak (Linux)                | `~/.var/app/tv.kodi.Kodi/data/temp/kodi.log`                          |
| Snap (Linux)                   | `~/snap/kodi/common/.kodi/temp/kodi.log`                              |
| Android                        | `/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/temp/kodi.log` |
| LibreELEC / CoreELEC           | `/storage/.kodi/temp/kodi.log`                                        |

When this doc says `~/.kodi/...`, substitute the right base path for your install.

The same naming applies to addon data — `userdata/addon_data/...` is under whichever base your Kodi uses.

## Enable Debug Logging

By default Kodi only logs INFO and above. Many useful messages are at DEBUG level. To enable:

**Settings → System → Logging → Enable debug logging** → On.

Restart Kodi after toggling. Then reproduce the problem and grab the log.

To turn it off again later (logs get big), flip the same setting back. The log file rotates on each Kodi restart — old log goes to `kodi.old.log`.

## Useful Log Searches

These all assume `~/.kodi/temp/kodi.log` — adjust the path for your install. If you're SSHing into a remote Kodi box, just prefix everything with `ssh user@host '...'`.

### Anything from this addon

```bash
grep "plugin.video.sweettv" ~/.kodi/temp/kodi.log
```

The addon logs everything with the prefix `[plugin.video.sweettv]`.

### IPTV Manager activity

```bash
grep "service.iptv.manager" ~/.kodi/temp/kodi.log | tail -50
```

Look for lines like:

```
[service.iptv.manager] Updating IPTV data for plugin.video.sweettv...
[service.iptv.manager] Requesting channels from plugin://plugin.video.sweettv/?action=iptv_channels&port={port}...
[service.iptv.manager] Executing RunPlugin(plugin://plugin.video.sweettv/?action=iptv_channels&port=43923)...
```

If you don't see these, IPTV Manager isn't being triggered. Either:

- Its service isn't running (check that `service.iptv.manager` shows up in the addon list and isn't disabled)
- Or the refresh interval hasn't elapsed (default 24h — use the manual "Force refresh now" action in IPTV Manager settings)

### PVR IPTV Simple Client

```bash
grep "pvr.iptvsimple" ~/.kodi/temp/kodi.log | tail -30
```

The most common useful line:

```
pvr.iptvsimple - ConnectionLost Could not validate M3U after startup
```

Means PVR Simple Client tried to read an M3U file but it was empty, missing, or pointed at the wrong path. See [Channels Don't Appear in TV](#channels-dont-appear-in-tv-section).

### Stream playback errors

```bash
grep -i "inputstream\|hls\|VideoPlayer\|sweettv" ~/.kodi/temp/kodi.log | grep -i "error\|fail\|warn" | tail -30
```

The notorious one:

```
inputstream.adaptive: Download failed, internal error: http://ads-badtest.sweet.tv/hls/badtest/...
```

This is the [ad preroll gotcha](api-reference.md#the-ad-preroll-gotcha). The addon now uses Kodi's built-in HLS player to avoid this — if you see it in current logs, you're either running an old build or someone reverted the fix.

### Addon install errors

```bash
grep -i "CAddonInfoBuilder\|sweettv" ~/.kodi/temp/kodi.log | tail -20
```

Common failures:

```
CAddonInfoBuilder::Generate: Unable to load 'zip://...': Failed to open file
```

→ The ZIP is corrupted, the path is sandboxed away from Kodi's reach (Flatpak), or `addon.xml` inside the ZIP is malformed.

```
CAddonInfoBuilder::Generate: Error reading Element value
```

→ `addon.xml` parses but Kodi's stricter XML validator rejects something. Usually a missing required attribute on an `<import>` tag, or a duplicate `xbmc.python.pluginsource` extension point.

## Enabling IPTV Manager Debug Logging

IPTV Manager has its own logging toggle, separate from Kodi's:

**Add-ons → My add-ons → Services → IPTV Manager → Configure → Expert → Enable debug logging**

After enabling, click **Force refresh now** in the same settings dialog to trigger an immediate refresh with verbose logs.

## Common Issues

### Addon Won't Install

**Symptom:** "Failed to install addon from zip file" or similar.

1. Grab the actual error from the log:

   ```bash
   grep -A2 -i "sweettv" ~/.kodi/temp/kodi.log | tail -20
   ```

2. **"Failed to unpack archive"** — The ZIP is in a directory Kodi can't read (Flatpak sandbox), is corrupted, or matches the version of an addon that's currently in a broken cached state. Try copying it to `~/.kodi/temp/` (or the equivalent userdata path) and installing from there.

3. **"Error reading Element value"** — `addon.xml` is malformed. Open the ZIP, extract `plugin.video.sweettv/addon.xml`, and validate with `xmllint --noout addon.xml`.

4. **Version conflict** — Kodi refuses to install a ZIP if an identical version is already installed. The Makefile auto-increments the version on every build (`YYYY.MM.DD.N`), so this should be rare.

### Addon Installs but Can't Find It

After install, the addon should appear under **Add-ons → Video add-ons → Sweet.TV**. If it's missing:

```bash
grep -i "FindAddons.*sweettv" ~/.kodi/temp/kodi.log
```

Should show `plugin.video.sweettv vYYYY.MM.DD.N installed`. If yes, restart Kodi — the addon list sometimes doesn't refresh.

If no, the install silently failed. Check the previous lines for the actual error.

### Pairing Code Not Accepted

**Symptom:** You enter the code at sweet.tv but the addon dialog times out without success.

1. Make sure you're entering the code at sweet.tv → **Profile → My Devices**, not the search box.
2. Click **Activate** on the website, not just enter the code.
3. The addon polls every 3 seconds for 5 minutes. If the website says the code is activated but the dialog still spins, look for `SigninService/GetStatus.json` errors in the log.

### Channels Don't Appear in TV Section

This is the #1 issue. The flow is:

1. Addon must be paired and logged in.
2. IPTV Manager service must be running.
3. IPTV Manager must have polled the addon (manually or scheduled).
4. The polled data must be written to `playlist.m3u8` and `epg.xml`.
5. PVR Simple Client must be configured to read those files.
6. Kodi must restart PVR Simple Client to pick up the new data.

Walk through it:

**Step 1 — addon logged in?**

Open the addon, browse channels. If you see them in the addon UI, login is fine.

**Step 2 — IPTV Manager service running?**

```bash
grep "service.iptv.manager" ~/.kodi/temp/kodi.log
```

Should show at least an `installed` line. If you don't see periodic activity, the service may be disabled or hasn't reached its refresh interval.

**Step 3 — manually trigger a refresh:**

In Kodi: **Add-ons → My add-ons → Services → IPTV Manager → Configure → Sources → Force refresh now**.

Then check the log immediately:

```bash
grep -i "iptv\|sweettv" ~/.kodi/temp/kodi.log | tail -30
```

You should see:

```
[service.iptv.manager] Updating IPTV data for plugin.video.sweettv...
[service.iptv.manager] Requesting channels from plugin://plugin.video.sweettv/?action=iptv_channels&port={port}...
[plugin.video.sweettv] IPTV Manager channels fetch starting
[plugin.video.sweettv] Providing N channels to IPTV Manager
[service.iptv.manager] Requesting epg from plugin://plugin.video.sweettv/?action=iptv_epg&port={port}...
[plugin.video.sweettv] EPG fetch starting, days=3
[plugin.video.sweettv] Fetching EPG for N channels x 3 days
[plugin.video.sweettv] EPG fetched: N channels with data
```

If you see all these but channels still don't appear, the issue is downstream (PVR Simple Client config).

**Step 4 — verify the M3U/EPG files were written:**

```bash
ls -la ~/.kodi/userdata/addon_data/service.iptv.manager/
```

You should see `playlist.m3u8` and `epg.xml` with recent timestamps and non-zero sizes. If they're missing or empty, the issue is in our addon side — check for errors after the "EPG fetched" log line.

**Step 5 — check PVR Simple Client paths:**

```bash
grep -A1 "m3uPath\|epgPath" ~/.kodi/userdata/addon_data/pvr.iptvsimple/instance-settings-1.xml
```

You want to see real values, not `default="true"` empty strings:

```xml
<setting id="m3uPathType">0</setting>
<setting id="m3uPath">/path/to/.../service.iptv.manager/playlist.m3u8</setting>
...
<setting id="epgPathType">0</setting>
<setting id="epgPath">/path/to/.../service.iptv.manager/epg.xml</setting>
```

`m3uPathType=0` means "Local Path". If it's `1` (Remote URL), PVR Simple is looking for the file in the wrong place.

To fix:

- **Auto:** **IPTV Manager settings → IPTV Simple → Configure IPTV Simple automatically**. This usually works.
- **Manual:** Open **PVR IPTV Simple Client → Configure → General**, set Location to **Local Path**, set the M3U path. Repeat in the EPG Settings tab. Use `special://userdata/addon_data/service.iptv.manager/playlist.m3u8` and `epg.xml` so the path is portable.

**Step 6 — restart Kodi.**

PVR Simple Client only reads the M3U/EPG at startup or when explicitly told to refresh. After changing paths or after a fresh poll from IPTV Manager, restart Kodi or trigger a PVR refresh.

### Stream Won't Play

**Symptom:** Click a channel, get an error notification or a black screen.

1. Check the log for the play_channel call:

   ```bash
   grep "play_channel\|sweettv" ~/.kodi/temp/kodi.log | tail -20
   ```

2. **HLS download errors** for `ads-badtest.sweet.tv` — known issue, see [Stream playback errors](#stream-playback-errors).

3. **"Too many devices"** in the API response — sweet.tv thinks you're streaming on too many devices. Either:
   - Kill any other sweet.tv apps using the same account
   - Open the addon's **Manage Devices** action and remove old/unused devices
   - Wait a minute for the server-side timeout to release stale slots

4. **"Not logged in"** dialog — token expired and refresh failed. Re-pair the device.

### Pinned Channels Empty or Wrong

Pinned channels are stored in `~/.kodi/userdata/addon_data/plugin.video.sweettv/favourites.json` (legacy filename from when the feature was called Favourites) as a JSON list of channel ID strings:

```json
["847", "952", "1364"]
```

If the list is corrupted, just delete the file. The addon will recreate it next time you pin a channel.

### Translations Not Showing

If you switched Kodi's UI language to Slovak/Czech but still see English in the addon:

1. Make sure you're running a build from `2026.04.06.20` or later (when localization was added).
2. Reinstall the addon — Kodi caches `.po` files and sometimes doesn't pick up new ones.
3. Check that the right `strings.po` file exists in `plugin.video.sweettv/resources/language/resource.language.<code>/`.

## Recovering Without Nuking Your Kodi

When things get into a really bad state, the temptation is to delete everything. Don't. Here's how to scope your recovery to just sweet.tv stuff.

### Reset just the Sweet.TV addon

```bash
rm -rf ~/.kodi/userdata/addon_data/plugin.video.sweettv
rm -rf ~/.kodi/addons/plugin.video.sweettv
```

This wipes tokens, pinned channels, settings, and the addon code itself. **Do not** delete `Addons*.db` from the database directory — that wipes Kodi's knowledge of every installed addon, not just ours. You'd have to reinstall everything.

After this, restart Kodi and reinstall the Sweet.TV ZIP. You'll need to re-pair.

### Clear just the Sweet.TV tokens (forces re-pair)

```bash
rm ~/.kodi/userdata/addon_data/plugin.video.sweettv/login.json
```

Settings and pinned channels are preserved.

### Force IPTV Manager to re-poll

```bash
rm ~/.kodi/userdata/addon_data/service.iptv.manager/playlist.m3u8
rm ~/.kodi/userdata/addon_data/service.iptv.manager/epg.xml
```

Then trigger **Force refresh now** in IPTV Manager settings.

### PVR database issues

If channels appear duplicated, missing, or stuck on old data, you can clear PVR's cached client database:

```bash
rm ~/.kodi/userdata/Database/TV*.db
```

Restart Kodi. PVR Simple Client will re-import everything from the M3U on startup. **This affects all PVR clients** — if you have other PVR sources configured, they'll need to re-sync too. They will, automatically, but it may take a minute.

## Getting a Log Off a Remote Box

If your Kodi is on another machine and you have SSH access:

```bash
# Get the last 50 lines of relevant entries
ssh user@kodi-box 'grep -i "sweettv\|iptv" ~/.kodi/temp/kodi.log | tail -50'
```

For Flatpak Kodi:

```bash
ssh user@kodi-box 'grep -i "sweettv\|iptv" ~/.var/app/tv.kodi.Kodi/data/temp/kodi.log | tail -50'
```

For paste-friendly capture of the whole log:

```bash
ssh user@kodi-box 'cat ~/.kodi/temp/kodi.log' > kodi-debug.log
```

## When All Else Fails

1. Enable debug logging in both Kodi and IPTV Manager.
2. Restart Kodi.
3. Reproduce the problem.
4. Grab the relevant log slice.
5. File an issue at <https://github.com/odlevakp/kodi-sweet.tv/issues> with the log and a description of what you did.
