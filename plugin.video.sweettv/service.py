# -*- coding: utf-8 -*-
"""Sweet.TV background service.

Handles:
- Stream lifecycle cleanup (closing streams when playback stops).
- IPTV Manager registration.
"""

import json

import xbmc
import xbmcaddon

from resources.lib.sweettv_api import SweetTVApi, _log


class SweetTVMonitor(xbmc.Monitor):
    """Monitor for addon settings changes and system events."""

    def __init__(self):
        super().__init__()
        self._active_stream_id = None

    def onNotification(self, sender, method, data):
        """Handle Kodi notifications."""
        # Listen for IPTV Manager requests.
        if method == "Other.sweettv_iptv_channels":
            _handle_iptv_request(data, "channels")
        elif method == "Other.sweettv_iptv_epg":
            _handle_iptv_request(data, "epg")


class SweetTVPlayer(xbmc.Player):
    """Player monitor to handle stream lifecycle."""

    def __init__(self):
        super().__init__()
        self._stream_id = None
        self._api = None

    def onAVStarted(self):
        """Called when playback starts."""
        try:
            item = self.getPlayingItem()
            stream_id = item.getProperty("sweettv_stream_id")
            if stream_id:
                self._stream_id = stream_id
                self._api = SweetTVApi()
                _log("Playback started, tracking stream_id: %s" % stream_id)
        except RuntimeError:
            pass

    def onPlayBackStopped(self):
        """Called when playback is stopped by user."""
        self._close_active_stream()

    def onPlayBackEnded(self):
        """Called when playback ends naturally."""
        self._close_active_stream()

    def _close_active_stream(self):
        """Close the active sweet.tv stream if any."""
        if self._stream_id and self._api:
            addon = xbmcaddon.Addon()
            if addon.getSettingBool("auto_close_stream"):
                _log("Closing stream: %s" % self._stream_id)
                self._api.close_stream(self._stream_id)
            self._stream_id = None
            self._api = None


def _register_iptv_manager():
    """Register with IPTV Manager if available."""
    try:
        iptv_addon = xbmcaddon.Addon("service.iptv.manager")
        _log("IPTV Manager found, registering...")

        # IPTV Manager uses addon.xml extension points for registration.
        # Our addon.xml declares the endpoints via the service entry point.
        # The actual registration happens via the IPTV Manager scanning
        # for addons that provide the iptv endpoints.
        _log("IPTV Manager integration active")
    except RuntimeError:
        _log("IPTV Manager not installed, native TV integration unavailable")


def _handle_iptv_request(data, request_type):
    """Handle IPTV Manager data requests."""
    from resources.lib.iptv_manager import IPTVManager

    try:
        parsed = json.loads(data)
        port = parsed.get("port", 0)
        if port:
            manager = IPTVManager(port)
            if request_type == "channels":
                manager.send_channels()
            elif request_type == "epg":
                manager.send_epg()
    except (json.JSONDecodeError, Exception) as e:
        _log("IPTV Manager request failed: %s" % e, level=xbmc.LOGERROR)


def main():
    """Main service loop."""
    _log("Sweet.TV service starting")

    monitor = SweetTVMonitor()
    player = SweetTVPlayer()

    _register_iptv_manager()

    # Service loop - wait for abort.
    while not monitor.abortRequested():
        if monitor.waitForAbort(10):
            break

    _log("Sweet.TV service stopped")


if __name__ == "__main__":
    main()
