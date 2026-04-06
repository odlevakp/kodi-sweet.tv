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
Content-type:    application/json
User-Agent:      Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
Origin:          https://sweet.tv
Referer:         https://sweet.tv
Accept-language: sk
x-device:        1;22;0;2;3.7.1
Authorization:   Bearer <access_token>     (omitted for SigninService/Start.json and SigninService/GetStatus.json)
```

The `x-device` header value and the `versionString` inside `device_info` (see below) must match — both should say `3.7.1`.

For fetching the actual HLS playlist (not the API), use the same headers but **drop** `Content-type` and `x-device`.

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
  "sub_type": 0,
  "firmware": {
    "versionCode": 1301,
    "versionString": "3.7.1"
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

### MovieService/GetConfiguration.json

Returns built-in movie genres and collections. Send `{}`.

Response (relevant fields):

```json
{
  "result": "OK",
  "genres":      [ { "id": 1, "title": "Action" }, ... ],
  "collections": [ { "id": 1, "title": "New Releases", "type": "Movie" }, ... ]
}
```

### MovieService/GetCollections.json

Get user-facing movie collections (different set than the built-in ones in `GetConfiguration`). Request: `{ "type": 1 }`. Returns objects with `id`, `title`, `type`. Filter for `type == "Movie"`.

### MovieService/GetCollectionMovies.json

Get movie IDs in a collection. Request: `{ "collection_id": <int> }`. Returns `{ "result": "OK", "movies": [<id>, <id>, ...] }`. Pass these IDs to `GetMovieInfo` to hydrate.

### MovieService/GetGenreMovies.json

Same as above but for a genre: `{ "genre_id": <int> }`.

### MovieService/GetMovieInfo.json

Hydrate a list of movie IDs into full objects.

Request:

```json
{
  "movies":              [123, 456],
  "need_bundle_offers":  false,
  "need_extended_info":  true
}
```

Response:

```json
{
  "result": "OK",
  "movies": [
    {
      "external_id_pairs": [
        { "external_id": 123, "owner_id": 7 }
      ],
      "title": "...",
      "description": "...",
      "poster_url": "...",
      "rating_imdb": 7.8,
      "duration": 5400,
      "year": "2024",
      "available": true,
      "trailer_url": "..."
    }
  ]
}
```

The `external_id` and `owner_id` from `external_id_pairs[0]` are what you pass to `GetLink`.

### MovieService/GetLink.json

Get a playable URL for a movie.

Request:

```json
{
  "movie_id":             123,
  "owner_id":             7,
  "audio_track":          -1,
  "preferred_link_type":  1,
  "subtitle":             "all"
}
```

Response:

```json
{
  "status": "OK",
  "link_type": "HLS",         // or "DASH"
  "url": "https://..."
}
```

DASH means Widevine — you'd need inputstream.adaptive with DRM keys (we don't currently support this). HLS plays with the built-in player or inputstream.adaptive.

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
