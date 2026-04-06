# -*- coding: utf-8 -*-
"""Sweet.TV API client for Kodi addon."""

import json
import os
import re
import time
import uuid

import requests
import xbmc
import xbmcaddon
import xbmcvfs


class SweetTVApi:
    """Client for the sweet.tv API."""

    API_BASE = "https://api.sweet.tv/"
    BILLING_BASE = "https://billing.sweet.tv/"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self._addon = xbmcaddon.Addon()
        self._profile_dir = xbmcvfs.translatePath(
            self._addon.getAddonInfo("profile")
        )
        os.makedirs(self._profile_dir, exist_ok=True)
        self._login_file = os.path.join(self._profile_dir, "login.json")

        self.device_id = None
        self.access_token = None
        self.refresh_token = None
        self.access_token_life = 0

        self._session = requests.Session()
        self._load_login_data()

        if self.device_id is None:
            self.device_id = str(uuid.uuid4())
            self._save_login_data()

    # -- Headers and device info ------------------------------------------

    @property
    def _common_headers(self):
        """Headers for API calls."""
        headers = {
            "User-Agent": self.USER_AGENT,
            "Origin": "https://sweet.tv",
            "Referer": "https://sweet.tv",
            "Accept-encoding": "gzip",
            "Accept-language": "en",
            "Content-type": "application/json",
            "x-device": "1;22;0;2;3.7.1",
        }
        if self.access_token:
            headers["Authorization"] = "Bearer " + self.access_token
        return headers

    @property
    def _stream_headers(self):
        """Headers for stream fetching (no content-type or x-device)."""
        return {
            "User-Agent": self.USER_AGENT,
            "Origin": "https://sweet.tv",
            "Referer": "https://sweet.tv",
            "Accept-encoding": "gzip",
            "Accept-language": "en",
        }

    @property
    def _device_info(self):
        """Device info payload sent with auth requests."""
        mac = ":".join(
            self.device_id.replace("-", "")[i * 2 : (i * 2) + 2]
            for i in range(6)
        )
        return {
            "type": "DT_AndroidTV",
            "mac": mac,
            "application": {"type": "AT_SWEET_TV_Player"},
            "sub_type": 0,
            "firmware": {"versionCode": 1301, "versionString": "3.7.1"},
            "uuid": self.device_id,
            "supported_drm": {"widevine_modular": True},
            "screen_info": {
                "aspectRatio": 6,
                "width": 1920,
                "height": 1080,
            },
            "advertisingId": str(uuid.uuid4()),
        }

    # -- Login persistence ------------------------------------------------

    def _load_login_data(self):
        """Load saved tokens from disk."""
        try:
            with open(self._login_file, "r") as f:
                data = json.load(f)
            if data.get("login_ver") == 2:
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.device_id = data.get("device_id")
                self.access_token_life = data.get("access_token_life", 0)
                _log("Login data loaded from cache")
            else:
                self.access_token = None
                self.refresh_token = None
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self.access_token = None

    def _save_login_data(self):
        """Persist tokens to disk."""
        try:
            if self.access_token:
                data = {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "access_token_life": self.access_token_life,
                    "login_ver": 2,
                    "device_id": self.device_id,
                }
                with open(self._login_file, "w") as f:
                    json.dump(data, f)
            else:
                if os.path.exists(self._login_file):
                    os.remove(self._login_file)
        except OSError as e:
            _log("Failed to save login data: %s" % e, level=xbmc.LOGERROR)

    # -- Core API call ----------------------------------------------------

    def _call_api(self, endpoint, data=None, auth=True, retry=True):
        """Make a POST request to the sweet.tv API.

        Returns parsed JSON response or empty dict on failure.
        """
        if not endpoint.startswith("http"):
            url = self.API_BASE + endpoint
        else:
            url = endpoint

        headers = dict(self._common_headers)
        if not auth:
            headers.pop("Authorization", None)

        try:
            resp = self._session.post(
                url,
                data=json.dumps(data or {}, separators=(",", ":")),
                headers=headers,
                timeout=15,
            )
        except requests.RequestException as e:
            _log("API request failed: %s" % e, level=xbmc.LOGERROR)
            return {}

        if resp.status_code == 200 or 400 <= resp.status_code < 500:
            try:
                result = resp.json()
            except ValueError:
                return {}

            # Handle expired token (code 16) with auto-retry.
            if (
                auth
                and retry
                and result.get("status") != "OK"
                and result.get("result") != "OK"
                and result.get("code") == 16
            ):
                _log("Token expired (code 16), refreshing...")
                if self.refresh_login():
                    return self._call_api(endpoint, data, auth=True, retry=False)

            return result

        _log(
            "Unexpected status %d from %s" % (resp.status_code, url),
            level=xbmc.LOGERROR,
        )
        return {}

    # -- Authentication ---------------------------------------------------

    def is_logged_in(self):
        """Check if we have valid credentials."""
        if not self.access_token:
            return False
        if self.access_token_life < int(time.time()):
            return self.refresh_login()
        return True

    def check_login(self):
        """Verify login by calling GetUserInfo."""
        if not self.access_token:
            return False
        if self.access_token_life < int(time.time()):
            if not self.refresh_login():
                return False
        data = self._call_api("TvService/GetUserInfo.json", data={})
        return data.get("status") == "OK"

    def get_signin_code(self):
        """Start device pairing and return the auth code."""
        data = self._call_api(
            "SigninService/Start.json",
            data={"device": self._device_info},
            auth=False,
            retry=False,
        )
        if data.get("result") != "OK" or "auth_code" not in data:
            _log("Failed to get signin code: %s" % data, level=xbmc.LOGERROR)
            return None
        return data["auth_code"]

    def check_signin_status(self, auth_code):
        """Poll pairing status. Returns True when completed."""
        data = self._call_api(
            "SigninService/GetStatus.json",
            data={"auth_code": auth_code},
            auth=False,
            retry=False,
        )
        if data.get("result") != "COMPLETED":
            return False

        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.access_token_life = data.get("expires_in", 0) + int(time.time())
        self._save_login_data()
        return True

    def refresh_login(self):
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            self.access_token = None
            return False

        _log("Refreshing access token")
        data = self._call_api(
            "AuthenticationService/Token.json",
            data={
                "device": self._device_info,
                "refresh_token": self.refresh_token,
            },
            retry=False,
        )

        if "access_token" not in data:
            _log("Token refresh failed: %s" % data, level=xbmc.LOGERROR)
            self.access_token = None
            self.refresh_token = None
            self.access_token_life = 0
            self._save_login_data()
            return False

        self.access_token = data["access_token"]
        self.access_token_life = data.get("expires_in", 0) + int(time.time())
        self._save_login_data()
        _log("Access token refreshed")
        return True

    def logout(self):
        """Logout and clear stored credentials."""
        if self.refresh_token:
            self._call_api(
                "SigninService/Logout.json",
                data={"refresh_token": self.refresh_token},
                retry=False,
            )
        self.access_token = None
        self.refresh_token = None
        self.access_token_life = 0
        self._save_login_data()

    # -- Channels ---------------------------------------------------------

    def get_channels(self):
        """Get list of available channels and categories.

        Returns (channels, categories) where channels is a list of dicts
        sorted by number, and categories is a list of {id, name} dicts.
        """
        data = self._call_api(
            "TvService/GetChannels.json",
            data={
                "need_epg": False,
                "need_list": True,
                "need_categories": True,
                "need_offsets": False,
                "need_hash": True,
                "need_icons": True,
                "need_big_icons": True,
            },
        )

        if data.get("status") != "OK":
            _log("Failed to load channels: %s" % data, level=xbmc.LOGERROR)
            return [], []

        categories = []
        for cat in data.get("categories") or []:
            categories.append(
                {
                    "id": cat.get("id"),
                    "name": cat.get("caption", ""),
                    "order": cat.get("order", 0),
                    "channel_list": cat.get("channel_list") or [],
                    "icon_url": cat.get("icon_url", ""),
                }
            )
        categories.sort(key=lambda c: c["order"])

        channels = []
        for ch in data.get("list") or []:
            if not ch.get("available"):
                continue
            channels.append(
                {
                    "id": str(ch["id"]),
                    "name": ch["name"],
                    "slug": ch.get("slug", ""),
                    "number": ch.get("number", 0),
                    "logo": ch.get("icon_url", ""),
                    "banner": ch.get("banner_url", ""),
                    "adult": (
                        1 in ch.get("category", [])
                        or "1" in ch.get("category", [])
                    ),
                    "categories": ch.get("category", []),
                    "catchup_days": (
                        ch.get("catchup_duration", 0)
                        if ch.get("catchup")
                        else 0
                    ),
                }
            )

        return sorted(channels, key=lambda c: c["number"]), categories

    # -- EPG --------------------------------------------------------------

    def get_epg(self, time_start=None, limit_next=1, channels=None):
        """Get EPG data for channels.

        Returns dict mapping channel_id -> list of epg events.
        """
        if time_start is None:
            time_start = int(time.time())

        req_data = {
            "epg_current_time": time_start,
            "epg_limit_next": limit_next,
            "epg_limit_prev": 0,
            "need_epg": True,
            "need_list": True,
            "need_categories": False,
            "need_offsets": False,
            "need_hash": False,
            "need_icons": False,
            "need_big_icons": False,
        }

        if channels:
            req_data["channels"] = channels

        data = self._call_api("TvService/GetChannels.json", data=req_data)

        if data.get("status") != "OK":
            _log("Failed to load EPG: %s" % data, level=xbmc.LOGERROR)
            return {}

        epg = {}
        for ch in data.get("list") or []:
            if "epg" in ch:
                epg[str(ch["id"])] = ch["epg"]

        return epg

    def get_epg_multi_day(self, channels, days=3):
        """Get EPG data spanning multiple days.

        Returns dict mapping channel_id -> list of all epg events.
        """
        now = int(time.time())
        all_epg = {}

        for day_offset in range(days):
            day_start = now - (now % 86400) + (day_offset * 86400)
            # Request enough events to cover a full day.
            epg = self.get_epg(
                time_start=day_start,
                limit_next=200,
                channels=channels,
            )
            for ch_id, events in epg.items():
                if ch_id not in all_epg:
                    all_epg[ch_id] = []
                # Deduplicate by event id.
                existing_ids = {e["id"] for e in all_epg[ch_id]}
                for event in events:
                    if event["id"] not in existing_ids:
                        all_epg[ch_id].append(event)
                        existing_ids.add(event["id"])

        return all_epg

    # -- Streams ----------------------------------------------------------

    def open_stream(self, channel_id, epg_id=None):
        """Open a stream for a channel. Returns (stream_url, stream_id) or (None, None)."""
        req_data = {
            "without_auth": True,
            "channel_id": channel_id,
            "accept_scheme": ["HTTP_HLS"],
            "multistream": True,
        }

        if epg_id:
            req_data["epg_id"] = epg_id

        data = self._call_api("TvService/OpenStream.json", data=req_data)

        if data.get("result") != "OK":
            _log(
                "Failed to open stream: %s" % data.get("message", ""),
                level=xbmc.LOGERROR,
            )
            return None, None

        hs = data["http_stream"]
        url = "http://%s:%d%s" % (
            hs["host"]["address"],
            hs["host"]["port"],
            hs["url"],
        )
        return url, data.get("stream_id")

    def close_stream(self, stream_id):
        """Close an open stream."""
        if not stream_id:
            return
        data = self._call_api(
            "TvService/CloseStream.json",
            data={"stream_id": int(stream_id)},
        )
        return data.get("result") == "OK"

    def resolve_hls_streams(self, master_url, max_bitrate=None):
        """Parse HLS master playlist and return variant streams.

        Returns list of dicts with url, bandwidth, resolution, name.
        """
        try:
            resp = self._session.get(
                master_url, headers=self._stream_headers, timeout=15
            )
        except requests.RequestException as e:
            _log("Failed to fetch HLS playlist: %s" % e, level=xbmc.LOGERROR)
            return []

        if resp.status_code != 200:
            _log(
                "HLS playlist HTTP %d" % resp.status_code,
                level=xbmc.LOGERROR,
            )
            return []

        if max_bitrate and int(max_bitrate) > 0:
            max_bps = int(max_bitrate) * 1_000_000
        else:
            max_bps = 100_000_000

        streams = []
        for m in re.finditer(
            r"^#EXT-X-STREAM-INF:(?P<info>.+)\n(?P<chunk>.+)",
            resp.text,
            re.MULTILINE,
        ):
            info = {}
            for part in re.split(
                r''',(?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', m.group("info")
            ):
                if "=" in part:
                    key, val = part.split("=", 1)
                    info[key.strip().lower()] = val.strip()

            stream_url = m.group("chunk").strip()
            # Resolve relative URLs.
            if not stream_url.startswith("http"):
                if stream_url.startswith("/"):
                    stream_url = (
                        master_url[: master_url[9:].find("/") + 9]
                        + stream_url
                    )
                else:
                    stream_url = (
                        master_url[: master_url.rfind("/") + 1] + stream_url
                    )

            bandwidth = int(info.get("bandwidth", 0))
            if bandwidth <= max_bps:
                resolution = info.get("resolution", "")
                streams.append(
                    {
                        "url": stream_url,
                        "bandwidth": bandwidth,
                        "resolution": resolution,
                        "name": resolution or ("%d kbps" % (bandwidth // 1000)),
                    }
                )

        return sorted(streams, key=lambda s: s["bandwidth"], reverse=True)

    def get_live_link(self, channel_id, epg_id=None, max_bitrate=None):
        """Get playable stream URL for a channel.

        Opens stream, resolves HLS variants, returns best URL and stream_id.
        """
        master_url, stream_id = self.open_stream(channel_id, epg_id)
        if not master_url:
            return None, None

        streams = self.resolve_hls_streams(master_url, max_bitrate)
        if not streams:
            self.close_stream(stream_id)
            return None, None

        # Return the highest quality stream within the bitrate limit.
        return streams[0]["url"], stream_id

    # -- Movies -----------------------------------------------------------

    def get_movie_configuration(self):
        """Get movie genres and built-in collections."""
        data = self._call_api("MovieService/GetConfiguration.json", data={})
        if data.get("result") != "OK":
            return None
        return data

    def get_movie_collections(self):
        """Get user-facing movie collections."""
        data = self._call_api(
            "MovieService/GetCollections.json", data={"type": 1}
        )
        if data.get("result") != "OK":
            return []
        return [c for c in (data.get("collection") or []) if c["type"] == "Movie"]

    def get_movie_collection(self, collection_id):
        """Get movies in a collection."""
        data = self._call_api(
            "MovieService/GetCollectionMovies.json",
            data={"collection_id": int(collection_id)},
        )
        if data.get("result") != "OK":
            return []
        movie_ids = data.get("movies")
        if not movie_ids:
            return []
        return self.get_movie_info(movie_ids)

    def get_movie_genre(self, genre_id):
        """Get movies in a genre."""
        data = self._call_api(
            "MovieService/GetGenreMovies.json",
            data={"genre_id": int(genre_id)},
        )
        if data.get("result") != "OK":
            return []
        movie_ids = data.get("movies")
        if not movie_ids:
            return []
        return self.get_movie_info(movie_ids)

    def get_movie_info(self, movie_ids):
        """Get detailed info for a list of movie IDs."""
        data = self._call_api(
            "MovieService/GetMovieInfo.json",
            data={
                "movies": movie_ids,
                "need_bundle_offers": False,
                "need_extended_info": True,
            },
        )
        if data.get("result") != "OK":
            return []

        movies = []
        for movie in data.get("movies") or []:
            ext_ids = movie.get("external_id_pairs", [{}])
            movies.append(
                {
                    "id": str(ext_ids[0].get("external_id", "")),
                    "owner_id": str(ext_ids[0].get("owner_id", "")),
                    "title": movie.get("title", ""),
                    "plot": movie.get("description", ""),
                    "poster": movie.get("poster_url", ""),
                    "rating": movie.get("rating_imdb"),
                    "duration": movie.get("duration"),
                    "year": int(movie["year"]) if movie.get("year") else None,
                    "available": movie.get("available", False),
                    "trailer": movie.get("trailer_url"),
                }
            )
        return movies

    def get_movie_link(self, movie_id, owner_id):
        """Get playable URL for a movie."""
        data = self._call_api(
            "MovieService/GetLink.json",
            data={
                "audio_track": -1,
                "movie_id": int(movie_id),
                "owner_id": int(owner_id),
                "preferred_link_type": 1,
                "subtitle": "all",
            },
        )
        if data.get("status") != "OK":
            return None, None
        if data.get("link_type") not in ("HLS", "DASH"):
            _log(
                "Unsupported movie stream type: %s" % data.get("link_type"),
                level=xbmc.LOGERROR,
            )
            return None, None
        return data["url"], data["link_type"]

    # -- Search -----------------------------------------------------------

    def search(self, query):
        """Search for movies and EPG records."""
        data = self._call_api(
            "SearchService/Search.json",
            data={"needle": query},
            retry=False,
        )

        results = {"movies": [], "events": []}
        movie_ids = []

        for item in data.get("result") or []:
            if item["type"] == "Movie":
                movie_ids.append(item["id"])
            elif item["type"] == "EpgRecord":
                results["events"].append(
                    {
                        "event_id": str(item["id"]),
                        "channel_id": str(item["sub_id"]),
                        "title": item["text"],
                        "poster": item.get("image_url", ""),
                        "time_start": item.get("time_start"),
                        "time_stop": item.get("time_stop"),
                    }
                )

        if movie_ids:
            results["movies"] = self.get_movie_info(movie_ids)

        return results

    # -- Device management ------------------------------------------------

    def get_devices(self):
        """List registered devices."""
        data = self._call_api(
            self.BILLING_BASE + "user/device/list", data={}, retry=False
        )
        return data.get("list", [])

    def remove_device(self, token_id):
        """Remove a registered device."""
        data = self._call_api(
            self.BILLING_BASE + "user/device/delete",
            data={"device_token_id": token_id},
            retry=False,
        )
        return data.get("result", False)

    # -- User info --------------------------------------------------------

    def get_user_info(self):
        """Get user/subscription info."""
        return self._call_api("TvService/GetUserInfo.json", data={})


def _log(msg, level=xbmc.LOGDEBUG):
    """Log a message to the Kodi log."""
    xbmc.log("[plugin.video.sweettv] %s" % msg, level=level)
