# -*- coding: utf-8 -*-
"""IPTV Manager integration for Sweet.TV.

Provides channels (M3U) and EPG (XMLTV) data to IPTV Manager,
which feeds them to PVR IPTV Simple Client for native TV experience.
"""

import json
import time
from datetime import datetime

import xbmc
import xbmcaddon

from .sweettv_api import SweetTVApi, _log, _vlog
from . import favourites


class IPTVManager:
    """Interface to IPTV Manager addon."""

    def __init__(self, port):
        """Initialize with the IPTV Manager callback port."""
        self.port = port

    def via_socket(self, func):
        """Send data to IPTV Manager via socket."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", self.port))
        try:
            sock.sendall(json.dumps(func()).encode())
        finally:
            sock.close()

    def send_channels(self):
        """Provide channel list to IPTV Manager."""
        self.via_socket(get_channels)

    def send_epg(self):
        """Provide EPG data to IPTV Manager."""
        self.via_socket(get_epg)


def get_channels():
    """Build channel list in IPTV Manager format.

    Returns dict with "version" and "streams" keys.
    """
    _vlog("IPTV Manager channels fetch starting")
    addon = xbmcaddon.Addon()
    show_adult = addon.getSettingBool("show_adult")

    api = SweetTVApi()
    if not api.is_logged_in():
        _vlog("Not logged in, returning empty channel list")
        return {"version": 1, "streams": []}

    channels, categories = api.get_channels()
    fav_ids = set(favourites.load())

    # Build a channel_id -> [category_name, ...] mapping from category channel_lists.
    # Skip the "All" category (id 1000) since it would group everything together.
    ch_to_groups = {}
    for cat in categories:
        if cat["id"] == 1000:
            continue
        # Skip adult category if disabled.
        if not show_adult and cat["id"] == 1:
            continue
        for cid in cat["channel_list"] or []:
            ch_to_groups.setdefault(str(cid), []).append(cat["name"])

    streams = []
    for ch in channels:
        if not show_adult and ch["adult"]:
            continue

        groups = list(ch_to_groups.get(ch["id"], []))
        # Add Pinned group if user has pinned this channel.
        if ch["id"] in fav_ids:
            groups.insert(0, "Pinned")
        # Fall back to "Sweet.TV" if a channel has no groups at all.
        if not groups:
            groups = ["Sweet.TV"]

        stream = {
            "name": ch["name"],
            "stream": "plugin://plugin.video.sweettv/?action=play_channel&channel_id=%s" % ch["id"],
            "id": "sweettv-%s" % ch["id"],
            "logo": ch["logo"],
            "preset": ch["number"],
            "group": ";".join(groups),
        }

        # Add catchup support if available.
        if ch["catchup_days"] > 0:
            stream["is_catchup"] = True
            stream["catchup_source"] = (
                "plugin://plugin.video.sweettv/"
                "?action=play_catchup"
                "&channel_id=%s"
                "&epg_id={catchup-id}" % ch["id"]
            )
            stream["catchup_days"] = ch["catchup_days"]

        streams.append(stream)

    _log("Providing %d channels to IPTV Manager" % len(streams))
    return {"version": 1, "streams": streams}


def get_epg():
    """Build EPG data in IPTV Manager format.

    Returns dict with "version" and "epg" keys.
    """
    addon = xbmcaddon.Addon()
    show_adult = addon.getSettingBool("show_adult")
    epg_days = addon.getSettingInt("epg_days")

    _vlog("EPG fetch starting, days=%d" % epg_days)

    api = SweetTVApi()
    if not api.is_logged_in():
        _vlog("Not logged in, returning empty EPG")
        return {"version": 1, "epg": {}}

    channels, _ = api.get_channels()
    channel_ids = []
    adult_ids = set()

    for ch in channels:
        if ch["adult"]:
            adult_ids.add(ch["id"])
            if not show_adult:
                continue
        channel_ids.append(int(ch["id"]))

    _vlog("Fetching EPG for %d channels x %d days" % (len(channel_ids), epg_days))
    epg_data = api.get_epg_multi_day(channel_ids, days=epg_days)
    _vlog("EPG fetched: %d channels with data" % len(epg_data))
    epg_result = {}

    for ch_id, events in epg_data.items():
        if ch_id in adult_ids and not show_adult:
            continue

        channel_key = "sweettv-%s" % ch_id
        epg_result[channel_key] = []

        # Strip "sweettv-" prefix to get the bare channel id for catchup URL.
        bare_channel_id = ch_id

        for event in events:
            start = datetime.utcfromtimestamp(int(event["time_start"]))
            stop = datetime.utcfromtimestamp(int(event["time_stop"]))

            epg_entry = {
                "start": start.strftime("%Y-%m-%d %H:%M:%S"),
                "stop": stop.strftime("%Y-%m-%d %H:%M:%S"),
                "title": event.get("text", ""),
                "episode-num": str(event.get("id", "")),
                # IPTV Manager passes 'stream' through as catchup-id in XMLTV.
                # PVR Simple Client uses it when the user picks "Play from EPG"
                # for a past program. The URL re-enters our addon with both
                # channel_id and epg_id so play_catchup can resolve the stream.
                "stream": (
                    "plugin://plugin.video.sweettv/?action=play_catchup"
                    "&channel_id=%s&epg_id=%s" % (bare_channel_id, event["id"])
                ),
            }

            if event.get("preview_url"):
                epg_entry["image"] = event["preview_url"]

            epg_result[channel_key].append(epg_entry)

    _log("Providing EPG for %d channels to IPTV Manager" % len(epg_result))
    return {"version": 1, "epg": epg_result}
