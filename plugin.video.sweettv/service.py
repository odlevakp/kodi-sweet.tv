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
    """Monitor for addon settings changes and system events.

    On Android TV, Kodi suspends instead of quitting when the TV turns
    off. PVR IPTV Simple Client loads channels at startup only, so after
    a long suspend the TV section can appear empty. We listen for resume
    signals (screensaver off, DPMS wake) and nudge PVR to re-scan.
    """

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

    def onScreensaverDeactivated(self):
        """Kodi woke from screensaver — nudge PVR to re-scan."""
        _nudge_pvr()

    def onDPMSDeactivated(self):
        """Display woke from power management (e.g. CEC TV turned on)."""
        _nudge_pvr()


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


def _nudge_pvr():
    """Ask PVR to re-import channels from all active clients.

    Uses the lightweight PVR.Scan JSON-RPC call which tells the PVR
    subsystem to re-read its sources without the risky disable/enable
    cycle that can crash PVR IPTV Simple Client.

    This runs on every screensaver/DPMS wake, which is frequent on
    Android TV (every time the TV turns on). The scan itself is cheap —
    PVR Simple Client just re-reads the M3U and EPG files it already has.
    """
    _log("Resume detected — nudging PVR to re-scan channels")
    try:
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "PVR.Scan",
            "id": 1,
        }))
    except Exception as e:
        _log("PVR.Scan failed: %s" % e, level=xbmc.LOGERROR)


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
