# Sweet.TV API Reference

Reverse-engineered from the [Enigma2 sweet.tv plugin](https://github.com/archivczsk/archivczsk-doplnky/tree/main/plugin_video_sweettv) and verified against the live API. This document captures everything you need to call the API directly.

The actual client implementation lives in [`sweettv_api.py`](../plugin.video.sweettv/resources/lib/sweettv_api.py).

## Base URLs

| URL                            | Used for                                  |
|--------------------------------|-------------------------------------------|
| `https://api.sweet.tv/`        | Everything except device management       |
| `https://billing.sweet.tv/`    | Listing/removing registered devices       |

All requests are **HTTP POST** with JSON body. Even read operations like getting channels use POST. There are no GET endpoints.

## Required Headers

```
Content-type:      application/json
User-Agent:        Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
Origin:            https://sweet.tv
Referer:           https://sweet.tv/
Accept-language:   sk-SK,sk;q=0.9,en-US;q=0.8,en;q=0.7
Content-type:      application/json
x-device:          1;22;39;2;7.4.50
x-device-id:       <device_id (uuid)>
x-accept-language: sk
Authorization:     Bearer <access_token>   (omitted for SigninService/Start.json and SigninService/GetStatus.json)
```

The `x-device` header encodes `app_type;device_type;sub_type;app_subtype;version`. The `versionString` inside `device_info` (see below) must match the version segment.

**Important**: an older `x-device` value (e.g. `1;22;0;2;3.7.1`) will work for live TV and channels but will get **empty responses** from the movie endpoints. The website currently sends `1;22;39;2;7.4.50` and that's what unlocks movies.

For fetching the actual HLS playlist (not the API), use the same headers but **drop** `Content-type`, `x-device`, and `x-device-id`.

## Authentication

Sweet.TV uses **device pairing**, not username/password. The flow:

1. Generate a random UUID, call it `device_id`. Persist it across runs.
2. `POST /SigninService/Start.json` with `{ "device": <device_info> }` (no auth header).
   Response includes `auth_code`.
3. Show `auth_code` to the user. They go to sweet.tv → My Devices → enter the code → Activate.
4. Poll `POST /SigninService/GetStatus.json` with `{ "auth_code": "<code>" }` (no auth header).
   - While pending: response has `result != "COMPLETED"`.
   - When done: response has `result: "COMPLETED"`, `access_token`, `refresh_token`, `expires_in`.
5. Persist `access_token`, `refresh_token`, `device_id`, and `access_token_life = now + expires_in`.

### Token Refresh

Access tokens expire (typically a few hours). Before each call, check if `access_token_life < now`. If so:

- `POST /AuthenticationService/Token.json` with `{ "device": <device_info>, "refresh_token": "<rt>" }`.
- Response: new `access_token` and `expires_in`.
- If this fails, both tokens are dead — wipe local data and force re-pairing.

### Code 16 Retry

If any authenticated call returns `code: 16` in the JSON body (regardless of HTTP status), the access token expired between checks. Refresh the token once and retry the request. Do not loop — if the retry also returns code 16, give up and force re-pairing.

### Logout

`POST /SigninService/Logout.json` with `{ "refresh_token": "<rt>" }`. Wipes the device on the server side too. After this, both tokens are invalid.

## Device Info Payload

Sent with `SigninService/Start.json` and `AuthenticationService/Token.json`:

```json
{
  "type": "DT_AndroidTV",
  "mac": "aa:bb:cc:dd:ee:ff",
  "application": { "type": "AT_SWEET_TV_Player" },
  "sub_type": 39,
  "firmware": {
    "versionCode": 1,
    "versionString": "7.4.50"
  },
  "uuid": "<device_id>",
  "supported_drm": { "widevine_modular": true },
  "screen_info": {
    "aspectRatio": 6,
    "width": 1920,
    "height": 1080
  },
  "advertisingId": "<random_uuid>"
}
```

The `mac` is derived from `device_id` by stripping hyphens and grouping the first 12 hex chars in colon-separated pairs. The `advertisingId` is a fresh random UUID per call.

## Endpoints

### TvService/GetUserInfo.json

Verify login status. Send `{}`. Response includes `status: "OK"` on success.

### TvService/GetChannels.json

Get channel list, categories, and/or EPG.

Request:

```json
{
  "need_epg":         true,           // include EPG events per channel
  "need_list":        true,           // include channels
  "need_categories":  true,           // include category list
  "need_offsets":     false,
  "need_hash":        true,
  "need_icons":       true,           // include channel icon URLs
  "need_big_icons":   true,           // include big icon URLs
  "epg_current_time": 1712345678,     // unix ts, used as anchor for EPG window
  "epg_limit_next":   1,              // events to return after current time
  "epg_limit_prev":   0,              // events to return before current time
  "channels":         [847, 848]      // optional filter
}
```

Response shape:

```json
{
  "status": "OK",
  "list_hash": "abc123",
  "list": [
    {
      "id": 847,
      "name": "Jednotka HD",
      "slug": "847-jednotka-hd",
      "number": 1,
      "available": true,
      "category": [20, 27, 32, 1000],          // category IDs this channel belongs to
      "catchup": true,
      "catchup_duration": 7,                    // days
      "icon_url": "http://staticeu.sweet.tv/...png",
      "banner_url": "http://staticeu.sweet.tv/...png",   // wider, higher-res
      "icon_v2_url": "...",
      "icon_small_url": "...",
      "dark_theme_icon_url": "...",
      "icon": "<base64 inline png>",
      "icon_big": "<base64 inline png>",
      "drm": false,
      "available_without_auth": true,
      "epg_days_past": 7,
      "epg_days_future": 2,
      "epg": [                                  // present when need_epg=true
        {
          "id": 12345,
          "text": "News at 7",
          "time_start": 1712345678,
          "time_stop":  1712349278,
          "preview_url": "http://..."
        }
      ]
    }
  ],
  "categories": [
    {
      "id": 20,
      "caption": "National",                     // NOTE: not "name"
      "order": 4,
      "icon_url": "http://staticeu.sweet.tv/images/v2/icons/categories/20.png",
      "channel_list": [847, 848, 952, ...],
      "slug": "nationwide-channels"
    }
  ]
}
```

Notes:

- Category id `1` = adult content. Filter client-side based on user setting.
- Category id `1000` = "All" — every channel ends up here.
- Category id `12` = "Favorite" but `channel_list` is always empty in the API response (sweet.tv tracks favourites elsewhere). Implement favourites client-side if you want them.
- Category sort order is in the `order` field, not the array position.
- Channel ordering for display should respect `number` (the channel preset number).

### TvService/OpenStream.json

Open a stream session. Required before playback.

Request (live):

```json
{
  "without_auth":  true,
  "channel_id":    847,
  "accept_scheme": ["HTTP_HLS"],
  "multistream":   true
}
```

Request (archive/catchup): same as above plus `"epg_id": <epg_event_id>`.

Response:

```json
{
  "result": "OK",
  "stream_id": 123456,
  "http_stream": {
    "host": {
      "address": "cdn.sweet.tv",
      "port": 80
    },
    "url": "/path/to/master.m3u8?token=..."
  }
}
```

Build the playable URL as:

```
http://{address}:{port}{url}
```

This URL is plain HTTP (not HTTPS) and points to an HLS master playlist.

#### The Ad Preroll Gotcha

The master playlist contains an ad preroll segment from `http://ads-badtest.sweet.tv/...` which **does not resolve** (the host is dead, intentional or not). `inputstream.adaptive` chokes on the failed segment download and refuses to play.

Workarounds:

1. Use Kodi's **built-in HLS player** (not inputstream.adaptive). It tolerates failed segments and skips past the ad. This is what the addon does.
2. Or fetch the master playlist yourself, parse out one variant URL from `#EXT-X-STREAM-INF` lines, and play that variant directly. The variant playlist also contains the ad preroll markers, but downstream players handle it better than inputstream.adaptive.

### TvService/CloseStream.json

Close an open stream. **You must call this** when playback ends or starts another stream — otherwise sweet.tv flags the device as "watching on too many devices" and rejects subsequent OpenStream calls.

Request:

```json
{ "stream_id": 123456 }
```

## Movies — How They Actually Stream

This is the part that took the longest to figure out. **Movies on sweet.tv are not served as VOD files.** They're scheduled as EPG events on premium movie channels (e.g. "Premium Comedy HD", "Top Movies HD") and streamed via the same `TvService/OpenStream` catchup mechanism that the live TV channels use.

The flow:

1. List movies via `MovieService/GetGenreMovies` or `MovieService/GetCollectionMovies` → get an array of movie IDs.
2. Bulk-hydrate via `MovieService/GetMovieInfo` (poster, title, year, rating). The bulk response does **not** include `channel_id`/`epg_id`.
3. When the user clicks play, call `MovieService/GetMovieInfo` again **for that single movie** with `need_extended_info: true`. The response now includes `channel_id` and `epg_id` — the catchup coordinates of the broadcast on a movie channel.
4. Call `TvService/OpenStream` with that `channel_id` + `epg_id` (the same way you'd play any catchup event).
5. The returned HLS playlist is the movie.

The schedule is per-broadcast — sweet.tv airs the same movie at different times on different premium channels, and the API returns whichever airing is currently relevant. If you cache the `(channel_id, epg_id)` pair for too long it will go stale.

### What Doesn't Work

`MovieService/GetLink.json` is **dead** for AVOD content. It always returns `{ "code": 5, "message": "Link not found" }` regardless of `preferred_link_type`. Older code (and the Enigma2 reference plugin) called this endpoint, which is why movies stopped working at some point.

Paid SVOD/TVOD movies (anything not `accessibility_model: ACCESSIBILITY_MODEL_AVOD`) likely use Widevine DRM via DASH, but we have not reverse-engineered that flow. The addon currently filters them out of the listing entirely.

### MovieService/GetConfiguration.json

Returns the static lookup tables: genres, collections, countries, languages, sort modes, video qualities, etc. Send `{}`.

Response keys: `result`, `categories`, `countries`, `genres`, `owners`, `roles`, `sort_modes`, `subgenres`, `video_qualities`, `languages`, `sections`, `cab_sections`, `currencies`.

A genre object looks like:

```json
{
  "id": 61,
  "title": "All movies",
  "slug": "all-movies",
  "icon_url": "http://staticeu.sweet.tv/...",
  "banner_url": "http://staticeu.sweet.tv/...",
  "icon_v2_url": "http://staticeu.sweet.tv/..."
}
```

A built-in collection object has `id`, `title`, and `type` (filter for `type == "Movie"`).

### MovieService/GetCollections.json

Get user-facing movie collections (a different set than the built-ins in `GetConfiguration`). Request: `{ "type": 1 }`. Returns objects with `id`, `title`, `type`. Filter for `type == "Movie"`.

### MovieService/GetCollectionMovies.json

Get movie IDs in a collection. Request: `{ "collection_id": <int> }`. Returns `{ "result": "OK", "movies": [<id>, <id>, ...] }`. Pass these IDs to `GetMovieInfo` to hydrate.

### MovieService/GetGenreMovies.json

Same shape as above but for a genre: `{ "genre_id": <int> }`. Returns `{ "result": "OK", "movies": [<id>, ...] }`.

**Important**: with the old `x-device` header (3.7.1) this returns `{ "result": "OK" }` with **no movies array**. You must use the current `x-device` value (`1;22;39;2;7.4.50`) for it to actually return data.

### MovieService/GetMovieInfo.json

Hydrate movie IDs into full objects. **Behaves differently in bulk vs single** — see below.

Request (bulk, used for listings):

```json
{
  "movies":              [123, 456, 789],
  "offset":              0,
  "limit":               20,
  "need_extended_info":  false
}
```

Bulk response per movie (truncated):

```json
{
  "id": 36461,
  "external_id_pairs": [{"owner_id": 191, "external_id": 36461, "preferred": true}],
  "title": "Miliardy",
  "year": 2016,
  "age_limit": 15,
  "poster_url": "http://...",
  "banner_url": "http://...",
  "rating_imdb": 8.3,
  "rating_kinopoisk": 6.5,
  "genres": [13],
  "available": true,
  "tagline": "",
  "slug": "36461-miliardy",
  "audio_tracks": [{"index": 24, "language": "Čeština", "sound_scheme": "Stereo", "iso_code": "cze"}],
  "released": true,
  "availability_info": "Zadarmo",
  "availability_info_color": "#1EBF85",
  "blurred_poster_url": "http://...",
  "promo_purchase_enabled": true,
  "scores": {"1": {"provider": "IMDB", "value": 8.3, "rating_count": 117470}},
  "accessibility_model": "ACCESSIBILITY_MODEL_AVOD"
}
```

Use `accessibility_model` to filter — only `ACCESSIBILITY_MODEL_AVOD` is playable without DRM.

Request (single movie, used to get playback coordinates):

```json
{
  "movies":              ["34205"],
  "offset":              0,
  "need_extended_info":  true
}
```

Single-movie response includes everything from the bulk response **plus** the critical fields:

```json
{
  "channel_id":     2005,
  "epg_id":         904970253,
  "duration":       5940,
  "description":    "...",
  "people":         [...],
  "video_qualities": [{"id": 2, "name": "", "height": 720, "file_size": "2664000000"}],
  "subtitles":      [{"language": "Čeština", "iso_code": "cze", "forced": false}],
  "recommended_movies": [...],
  "statistics":     {"like_count": 7, "dislike_count": 1}
}
```

`channel_id` and `epg_id` are the catchup coordinates passed to `TvService/OpenStream` for playback. **These fields are NOT returned by the bulk request**, even with `need_extended_info: true` — only single-movie requests get them.

The `external_id_pairs[0].external_id` is the movie ID and `owner_id` identifies the content provider; both are needed for tracking and `MovieService/GetLink` calls (though as noted, GetLink is currently dead).

### MovieService/GetLink.json

**Currently broken / unused for AVOD.** Always returns `{ "code": 5, "message": "Link not found" }`. Listed here for completeness — the Enigma2 plugin and older versions of this addon called it.

The intended request format was:

```json
{
  "movie_id":             123,
  "owner_id":             7,
  "audio_track":          -1,
  "preferred_link_type":  1,
  "subtitle":             "all"
}
```

If you find a working invocation, please open an issue.

### SearchService/Search.json

Search both movies and EPG records.

Request: `{ "needle": "query string" }`.

Response:

```json
{
  "result": [
    {
      "type": "Movie",
      "id":   123,
      "text": "...",
      "image_url": "..."
    },
    {
      "type":       "EpgRecord",
      "id":         12345,        // epg_id
      "sub_id":     847,          // channel_id
      "text":       "...",
      "image_url":  "...",
      "time_start": 1712345678,
      "time_stop":  1712349278
    }
  ]
}
```

For movie hits, follow up with `GetMovieInfo` to get details. EpgRecord hits are directly playable as catchup (if the channel supports it) using `(channel_id, epg_id)`.

## Billing API

Used for device management. Different base URL but same auth header and POST/JSON convention.

### user/device/list

Send `{}`. Returns `{ "list": [ {device}, ... ] }` where each device has `date_added`, `model`, `type`, `token_id`.

### user/device/delete

Send `{ "device_token_id": "<token_id>" }`. Returns `{ "result": true }` on success.

## Stream Lifecycle Summary

1. `OpenStream` — get URL + `stream_id`
2. Play
3. `CloseStream` with the `stream_id` when playback ends, the user stops, or another stream is opened
4. If you skip step 3 enough times, the user will get "too many devices" errors and need to manually unregister something via the billing API or the sweet.tv website

## Error Conventions

- HTTP 200 means "API responded" — not "operation succeeded".
- Check `status: "OK"` (used by TvService) or `result: "OK"` / `result: "COMPLETED"` (used by other services). Inconsistent across services.
- Error responses sometimes include `code` and `message`. The most important code is `16` (token expired, see [Code 16 Retry](#code-16-retry)).
- Unsupported HTTP errors (5xx, network failures) bubble up as exceptions.

## Things This Document Does Not Cover

- DRM/Widevine flow for protected DASH streams (the addon does not currently support this).
- Subscription/billing details — `GetUserInfo` returns subscription info but the field names haven't been mapped yet.
- Recommendations / continue-watching endpoints (not used by this addon).
- The `RadioService/*` endpoints if they exist.
