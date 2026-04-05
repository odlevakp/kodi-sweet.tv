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

from .sweettv_api import SweetTVApi, _log


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
    addon = xbmcaddon.Addon()
    show_adult = addon.getSettingBool("show_adult")

    api = SweetTVApi()
    if not api.is_logged_in():
        _log("Not logged in, returning empty channel list")
        return {"version": 1, "streams": []}

    channels, _ = api.get_channels()
    streams = []

    for ch in channels:
        if not show_adult and ch["adult"]:
            continue

        stream = {
            "name": ch["name"],
            "stream": "plugin://plugin.video.sweettv/?action=play_channel&channel_id=%s" % ch["id"],
            "id": "sweettv-%s" % ch["id"],
            "logo": ch["logo"],
            "preset": ch["number"],
            "group": "Sweet.TV",
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

    api = SweetTVApi()
    if not api.is_logged_in():
        _log("Not logged in, returning empty EPG")
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

    epg_data = api.get_epg_multi_day(channel_ids, days=epg_days)
    epg_result = {}

    for ch_id, events in epg_data.items():
        if ch_id in adult_ids and not show_adult:
            continue

        channel_key = "sweettv-%s" % ch_id
        epg_result[channel_key] = []

        for event in events:
            start = datetime.utcfromtimestamp(int(event["time_start"]))
            stop = datetime.utcfromtimestamp(int(event["time_stop"]))

            epg_entry = {
                "start": start.strftime("%Y-%m-%d %H:%M:%S"),
                "stop": stop.strftime("%Y-%m-%d %H:%M:%S"),
                "title": event.get("text", ""),
                "episode-num": str(event.get("id", "")),
            }

            if event.get("preview_url"):
                epg_entry["image"] = event["preview_url"]

            epg_result[channel_key].append(epg_entry)

    _log("Providing EPG for %d channels to IPTV Manager" % len(epg_result))
    return {"version": 1, "epg": epg_result}
