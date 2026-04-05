# -*- coding: utf-8 -*-
"""Sweet.TV Kodi addon entry point.

Handles URL routing for plugin:// calls from Kodi and IPTV Manager.
"""

import sys
from urllib.parse import parse_qs, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.sweettv_api import SweetTVApi, _log
from resources.lib.iptv_manager import IPTVManager


def main():
    """Route incoming plugin:// calls to the appropriate handler."""
    url = urlparse(sys.argv[0])
    handle = int(sys.argv[1])
    params = parse_qs(sys.argv[2].lstrip("?"))

    action = params.get("action", [None])[0]
    _log("Action: %s, Params: %s" % (action, params))

    if action is None:
        show_main_menu(handle)
    elif action == "browse_channels":
        browse_channels(handle)
    elif action == "play_channel":
        play_channel(handle, params)
    elif action == "play_catchup":
        play_catchup(handle, params)
    elif action == "pair_device":
        pair_device()
    elif action == "unpair_device":
        unpair_device()
    elif action == "manage_devices":
        manage_devices(handle)
    elif action == "remove_device":
        remove_device(params)
    elif action == "subscription_info":
        show_subscription_info()
    elif action == "iptv_channels":
        # IPTV Manager callback.
        port = int(params.get("port", [0])[0])
        IPTVManager(port).send_channels()
    elif action == "iptv_epg":
        # IPTV Manager callback.
        port = int(params.get("port", [0])[0])
        IPTVManager(port).send_epg()
    elif action == "browse_archive":
        browse_archive(handle, params)
    elif action == "archive_day":
        archive_day(handle, params)
    elif action == "browse_movies":
        browse_movies(handle, params)
    elif action == "movie_genre":
        movie_genre(handle, params)
    elif action == "movie_collection":
        movie_collection(handle, params)
    elif action == "play_movie":
        play_movie(handle, params)
    elif action == "search":
        search(handle, params)
    else:
        _log("Unknown action: %s" % action, level=xbmc.LOGWARNING)
        show_main_menu(handle)


# -- Main menu -----------------------------------------------------------


def show_main_menu(handle):
    """Show the addon's main navigation menu."""
    addon = xbmcaddon.Addon()
    items = [
        ("Live TV", "browse_channels", "DefaultTVShows.png", True),
        ("Archive", "browse_archive", "DefaultYear.png", True),
        ("Movies", "browse_movies", "DefaultMovies.png", True),
        ("Search", "search", "DefaultAddonsSearch.png", True),
    ]

    for label, action, icon, is_folder in items:
        url = "plugin://plugin.video.sweettv/?action=%s" % action
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": icon})
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle)


# -- Live TV channel list ------------------------------------------------


def browse_channels(handle):
    """Show list of live TV channels."""
    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", "Not logged in. Please pair your device first.")
        return

    addon = xbmcaddon.Addon()
    show_adult = addon.getSettingBool("show_adult")
    channels = api.get_channels()

    # Get current EPG for channel descriptions.
    channel_ids = [int(ch["id"]) for ch in channels]
    epg = api.get_epg(limit_next=1, channels=channel_ids)

    for ch in channels:
        if not show_adult and ch["adult"]:
            continue

        label = ch["name"]
        info = {"title": ch["name"]}

        # Show current program in the label.
        ch_epg = epg.get(ch["id"], [])
        img = ch.get("logo")
        if ch_epg:
            event = ch_epg[0]
            from datetime import datetime
            start = datetime.fromtimestamp(int(event["time_start"])).strftime("%H:%M")
            stop = datetime.fromtimestamp(int(event["time_stop"])).strftime("%H:%M")
            label = "%s - [I]%s[/I]" % (ch["name"], event.get("text", ""))
            info["plot"] = "%s - %s\n%s" % (start, stop, event.get("text", ""))
            if event.get("preview_url"):
                img = event["preview_url"]

        url = "plugin://plugin.video.sweettv/?action=play_channel&channel_id=%s" % ch["id"]
        li = xbmcgui.ListItem(label)
        li.setInfo("video", info)
        li.setArt({"icon": ch.get("logo", ""), "thumb": img})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)


# -- Live TV playback ----------------------------------------------------


def play_channel(handle, params):
    """Play a live TV channel."""
    channel_id = params.get("channel_id", [None])[0]
    if not channel_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", "Not logged in. Please pair your device first.")
        return

    addon = xbmcaddon.Addon()
    max_bitrate_str = addon.getSetting("max_bitrate")
    max_bitrate = _parse_bitrate(max_bitrate_str)

    stream_url, stream_id = api.get_live_link(channel_id, max_bitrate=max_bitrate)
    if not stream_url:
        xbmcgui.Dialog().notification("Sweet.TV", "Failed to load stream", xbmcgui.NOTIFICATION_ERROR)
        return

    li = xbmcgui.ListItem(path=stream_url)

    if addon.getSettingBool("use_inputstream"):
        li.setProperty("inputstream", "inputstream.adaptive")
        li.setProperty("inputstream.adaptive.manifest_type", "hls")

    li.setProperty("inputstream.adaptive.stream_headers", "User-Agent=%s" % SweetTVApi.USER_AGENT)

    # Store stream_id for cleanup.
    if stream_id:
        li.setProperty("sweettv_stream_id", str(stream_id))

    xbmcplugin.setResolvedUrl(handle, True, li)


# -- Catchup/Archive playback -------------------------------------------


def play_catchup(handle, params):
    """Play a catchup/archive stream."""
    channel_id = params.get("channel_id", [None])[0]
    epg_id = params.get("epg_id", [None])[0]
    if not channel_id or not epg_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", "Not logged in. Please pair your device first.")
        return

    addon = xbmcaddon.Addon()
    max_bitrate_str = addon.getSetting("max_bitrate")
    max_bitrate = _parse_bitrate(max_bitrate_str)

    stream_url, stream_id = api.get_live_link(
        channel_id, epg_id=int(epg_id), max_bitrate=max_bitrate
    )
    if not stream_url:
        xbmcgui.Dialog().notification("Sweet.TV", "Failed to load archive stream", xbmcgui.NOTIFICATION_ERROR)
        return

    li = xbmcgui.ListItem(path=stream_url)

    if addon.getSettingBool("use_inputstream"):
        li.setProperty("inputstream", "inputstream.adaptive")
        li.setProperty("inputstream.adaptive.manifest_type", "hls")

    li.setProperty("inputstream.adaptive.stream_headers", "User-Agent=%s" % SweetTVApi.USER_AGENT)

    if stream_id:
        li.setProperty("sweettv_stream_id", str(stream_id))

    xbmcplugin.setResolvedUrl(handle, True, li)


# -- Archive browsing ----------------------------------------------------


def browse_archive(handle, params):
    """Show list of channels that have archive/catchup support."""
    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", "Not logged in. Please pair your device first.")
        return

    addon = xbmcaddon.Addon()
    show_adult = addon.getSettingBool("show_adult")
    channels = api.get_channels()

    for ch in channels:
        if not show_adult and ch["adult"]:
            continue
        if ch["catchup_days"] <= 0:
            continue

        url = (
            "plugin://plugin.video.sweettv/"
            "?action=archive_day&channel_id=%s&catchup_days=%d"
            % (ch["id"], ch["catchup_days"])
        )
        li = xbmcgui.ListItem(ch["name"])
        li.setArt({"icon": ch["logo"], "thumb": ch["logo"]})
        li.setInfo("video", {"title": ch["name"], "plot": "Archive: %d days" % ch["catchup_days"]})
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle)


def archive_day(handle, params):
    """Show archive programs for a channel on a given day."""
    import time as _time
    from datetime import datetime, timedelta

    channel_id = params.get("channel_id", [None])[0]
    catchup_days = int(params.get("catchup_days", [7])[0])
    day_offset = int(params.get("day_offset", [-1])[0])

    if not channel_id:
        return

    # If no day selected, show day picker.
    if day_offset < 0:
        now = datetime.now()
        for i in range(catchup_days):
            day = now - timedelta(days=i)
            if i == 0:
                label = "Today - %s" % day.strftime("%d.%m.%Y")
            elif i == 1:
                label = "Yesterday - %s" % day.strftime("%d.%m.%Y")
            else:
                label = day.strftime("%A - %d.%m.%Y")

            url = (
                "plugin://plugin.video.sweettv/"
                "?action=archive_day&channel_id=%s&catchup_days=%d&day_offset=%d"
                % (channel_id, catchup_days, i)
            )
            li = xbmcgui.ListItem(label)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        xbmcplugin.endOfDirectory(handle)
        return

    # Show programs for the selected day.
    api = SweetTVApi()
    if not api.is_logged_in():
        return

    now = _time.time()
    day_start = int(now) - (int(now) % 86400) - (day_offset * 86400)
    day_end = day_start + 86400

    epg = api.get_epg(
        time_start=day_start,
        limit_next=200,
        channels=[int(channel_id)],
    )

    events = epg.get(channel_id, [])
    for event in events:
        start_ts = int(event["time_start"])
        stop_ts = int(event["time_stop"])

        if start_ts < day_start:
            continue
        if start_ts >= day_end:
            break

        start_str = datetime.fromtimestamp(start_ts).strftime("%H:%M")
        stop_str = datetime.fromtimestamp(stop_ts).strftime("%H:%M")
        title = event.get("text", "")
        label = "%s - %s  %s" % (start_str, stop_str, title)

        url = (
            "plugin://plugin.video.sweettv/"
            "?action=play_catchup&channel_id=%s&epg_id=%s"
            % (channel_id, event["id"])
        )
        li = xbmcgui.ListItem(label)
        li.setInfo("video", {"title": title})
        if event.get("preview_url"):
            li.setArt({"thumb": event["preview_url"]})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)


# -- Movies browsing -----------------------------------------------------


def browse_movies(handle, params):
    """Show movie browsing options (by genre, by collection)."""
    cat = params.get("cat", [None])[0]

    if cat is None:
        for label, cat_id in [("By Genre", "genres"), ("By Collection", "collections")]:
            url = "plugin://plugin.video.sweettv/?action=browse_movies&cat=%s" % cat_id
            li = xbmcgui.ListItem(label)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        xbmcplugin.endOfDirectory(handle)
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        return

    config = api.get_movie_configuration()
    if not config:
        return

    if cat == "genres":
        for genre in config.get("genres", []):
            url = "plugin://plugin.video.sweettv/?action=movie_genre&genre_id=%s" % genre["id"]
            li = xbmcgui.ListItem(genre["title"])
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    elif cat == "collections":
        collections = config.get("collections", []) + api.get_movie_collections()
        for col in collections:
            url = "plugin://plugin.video.sweettv/?action=movie_collection&collection_id=%s" % col["id"]
            li = xbmcgui.ListItem(col["title"])
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle)


def movie_genre(handle, params):
    """Show movies in a genre."""
    genre_id = params.get("genre_id", [None])[0]
    if not genre_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        return

    movies = api.get_movie_genre(genre_id)
    _list_movies(handle, movies)


def movie_collection(handle, params):
    """Show movies in a collection."""
    collection_id = params.get("collection_id", [None])[0]
    if not collection_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        return

    movies = api.get_movie_collection(collection_id)
    _list_movies(handle, movies)


def play_movie(handle, params):
    """Play a movie."""
    movie_id = params.get("movie_id", [None])[0]
    owner_id = params.get("owner_id", [None])[0]
    if not movie_id or not owner_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        return

    url, link_type = api.get_movie_link(movie_id, owner_id)
    if not url:
        xbmcgui.Dialog().notification("Sweet.TV", "Failed to load movie", xbmcgui.NOTIFICATION_ERROR)
        return

    li = xbmcgui.ListItem(path=url)

    addon = xbmcaddon.Addon()
    if addon.getSettingBool("use_inputstream"):
        li.setProperty("inputstream", "inputstream.adaptive")
        if link_type == "DASH":
            li.setProperty("inputstream.adaptive.manifest_type", "mpd")
        else:
            li.setProperty("inputstream.adaptive.manifest_type", "hls")

    xbmcplugin.setResolvedUrl(handle, True, li)


def _list_movies(handle, movies):
    """Add movie items to the directory listing."""
    addon = xbmcaddon.Addon()
    show_paid = True  # TODO: add setting for this.

    for movie in movies:
        if not movie["available"] and not show_paid:
            continue

        title = movie["title"]
        if not movie["available"]:
            title = "[COLOR yellow]*[/COLOR] " + title

        url = (
            "plugin://plugin.video.sweettv/"
            "?action=play_movie&movie_id=%s&owner_id=%s"
            % (movie["id"], movie["owner_id"])
        )
        li = xbmcgui.ListItem(title)
        info = {"title": movie["title"]}
        if movie.get("plot"):
            info["plot"] = movie["plot"]
        if movie.get("year"):
            info["year"] = movie["year"]
        if movie.get("duration"):
            info["duration"] = movie["duration"]
        if movie.get("rating"):
            info["rating"] = float(movie["rating"])
        li.setInfo("video", info)
        if movie.get("poster"):
            li.setArt({"poster": movie["poster"], "thumb": movie["poster"]})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)


# -- Search --------------------------------------------------------------


def search(handle, params):
    """Search for movies and EPG records."""
    query = params.get("query", [None])[0]
    if not query:
        keyboard = xbmc.Keyboard("", "Search Sweet.TV")
        keyboard.doModal()
        if not keyboard.isConfirmed():
            return
        query = keyboard.getText()
        if not query:
            return

    api = SweetTVApi()
    if not api.is_logged_in():
        return

    results = api.search(query)

    for movie in results.get("movies", []):
        url = (
            "plugin://plugin.video.sweettv/"
            "?action=play_movie&movie_id=%s&owner_id=%s"
            % (movie["id"], movie["owner_id"])
        )
        li = xbmcgui.ListItem("[Movie] " + movie["title"])
        if movie.get("poster"):
            li.setArt({"poster": movie["poster"], "thumb": movie["poster"]})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    for event in results.get("events", []):
        from datetime import datetime
        start = datetime.fromtimestamp(int(event["time_start"])).strftime("%d.%m. %H:%M")
        stop = datetime.fromtimestamp(int(event["time_stop"])).strftime("%H:%M")
        label = "[Archive] %s (%s - %s)" % (event["title"], start, stop)

        url = (
            "plugin://plugin.video.sweettv/"
            "?action=play_catchup&channel_id=%s&epg_id=%s"
            % (event["channel_id"], event["event_id"])
        )
        li = xbmcgui.ListItem(label)
        if event.get("poster"):
            li.setArt({"thumb": event["poster"]})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)


# -- Device pairing ------------------------------------------------------


def pair_device():
    """Start the device pairing flow."""
    api = SweetTVApi()

    if api.is_logged_in():
        if not xbmcgui.Dialog().yesno(
            "Sweet.TV",
            "Already paired. Do you want to re-pair?"
        ):
            return
        api.logout()

    code = api.get_signin_code()
    if not code:
        xbmcgui.Dialog().ok("Sweet.TV", "Failed to get pairing code. Please try again.")
        return

    dialog = xbmcgui.DialogProgress()
    dialog.create(
        "Sweet.TV - Device Pairing",
        "Your pairing code is: [B]%s[/B]\n\n"
        "Go to sweet.tv, log in to your account,\n"
        "navigate to My Devices, enter this code,\n"
        "and click Activate.\n\n"
        "Waiting for pairing..." % code,
    )

    # Poll for up to 5 minutes.
    timeout = 300
    interval = 3
    elapsed = 0

    while elapsed < timeout:
        if dialog.iscanceled():
            dialog.close()
            return

        dialog.update(int(elapsed / timeout * 100))

        if api.check_signin_status(code):
            dialog.close()
            xbmcgui.Dialog().ok("Sweet.TV", "Device paired successfully!")
            return

        xbmc.sleep(interval * 1000)
        elapsed += interval

    dialog.close()
    xbmcgui.Dialog().ok("Sweet.TV", "Pairing timed out. Please try again.")


def unpair_device():
    """Logout and clear credentials."""
    if not xbmcgui.Dialog().yesno("Sweet.TV", "Are you sure you want to unpair this device?"):
        return

    api = SweetTVApi()
    api.logout()
    xbmcgui.Dialog().ok("Sweet.TV", "Device unpaired successfully.")


# -- Device management ---------------------------------------------------


def manage_devices(handle):
    """Show list of registered devices."""
    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", "Not logged in.")
        return

    devices = api.get_devices()
    if not devices:
        xbmcgui.Dialog().ok("Sweet.TV", "No devices found.")
        return

    from datetime import datetime

    for dev in devices:
        date_str = datetime.fromtimestamp(int(dev.get("date_added", 0))).strftime("%d.%m.%Y %H:%M")
        label = "%s (%s) - Added: %s" % (
            dev.get("model", "Unknown"),
            dev.get("type", "Unknown"),
            date_str,
        )
        url = (
            "plugin://plugin.video.sweettv/"
            "?action=remove_device&token_id=%s" % dev.get("token_id", "")
        )
        li = xbmcgui.ListItem(label)
        li.setInfo("video", {"plot": "Select to remove this device"})
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)


def remove_device(params):
    """Remove a registered device."""
    token_id = params.get("token_id", [None])[0]
    if not token_id:
        return

    if not xbmcgui.Dialog().yesno("Sweet.TV", "Remove this device?"):
        return

    api = SweetTVApi()
    api.remove_device(token_id)
    xbmcgui.Dialog().ok("Sweet.TV", "Device removed.")
    xbmc.executebuiltin("Container.Refresh")


# -- Subscription info ---------------------------------------------------


def show_subscription_info():
    """Show subscription details in a dialog."""
    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", "Not logged in.")
        return

    info = api.get_user_info()
    if info.get("status") != "OK":
        xbmcgui.Dialog().ok("Sweet.TV", "Failed to load subscription info.")
        return

    # Format whatever info the API returns.
    lines = ["Status: Active"]
    for key in ("tariff_name", "tariff", "balance", "end_date", "subscription_end"):
        if key in info:
            label = key.replace("_", " ").title()
            lines.append("%s: %s" % (label, info[key]))

    xbmcgui.Dialog().textviewer("Sweet.TV - Subscription", "\n".join(lines))


# -- Helpers -------------------------------------------------------------


def _parse_bitrate(setting_value):
    """Parse bitrate setting string to integer Mbit/s or None."""
    if not setting_value or setting_value == "Unlimited":
        return None
    try:
        return int(setting_value.split()[0])
    except (ValueError, IndexError):
        return None


if __name__ == "__main__":
    main()
