# -*- coding: utf-8 -*-
"""Sweet.TV Kodi addon entry point.

Handles URL routing for plugin:// calls from Kodi and IPTV Manager.
"""

import os
import sys
from urllib.parse import parse_qs, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.sweettv_api import (
    SweetTVApi, _log, _vlog,
    show_adult_allowed, is_adult_unlocked, set_adult_unlocked,
)
from resources.lib.iptv_manager import IPTVManager
from resources.lib import favourites
from resources.lib.strings import M, t as _t


def main():
    """Route incoming plugin:// calls to the appropriate handler."""
    url = urlparse(sys.argv[0])
    handle = int(sys.argv[1])
    params = parse_qs(sys.argv[2].lstrip("?"))

    action = params.get("action", [None])[0]
    _log("Action: %s, Params: %s" % (action, params))

    # Auto-trigger pairing on first use. Skip for actions that handle
    # the not-logged-in state themselves or shouldn't trigger UI.
    _PAIRING_EXEMPT = {
        "pair_device", "unpair_device",
        "iptv_channels", "iptv_epg",
        "fav_add", "fav_remove", "fav_up", "fav_down",
    }
    if action not in _PAIRING_EXEMPT:
        api = SweetTVApi()
        if not api.is_logged_in():
            _vlog("Not logged in - launching pairing flow")
            pair_device()
            # If still not logged in (user cancelled), bail out cleanly.
            if not SweetTVApi().is_logged_in():
                if action is None:
                    # Show empty main menu so the addon "opens" without error.
                    xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False)
                return

    if action is None:
        show_main_menu(handle)
    elif action == "browse_channels":
        browse_channels(handle, params)
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
    elif action == "open_settings":
        xbmcaddon.Addon().openSettings()
    elif action == "configure_pvr":
        configure_pvr_simple()
    elif action == "setup_pvr":
        setup_pvr_integration()
    elif action == "add_kodi_favourite":
        add_kodi_favourite(params)
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
    elif action == "movie_info":
        show_movie_info(params)
    elif action == "search":
        search(handle, params)
    elif action == "fav_add":
        favourites.add(params.get("channel_id", [""])[0])
        xbmcgui.Dialog().notification("Sweet.TV", _t(M.FAV_ADDED))
        xbmc.executebuiltin("Container.Refresh")
    elif action == "fav_remove":
        favourites.remove(params.get("channel_id", [""])[0])
        xbmcgui.Dialog().notification("Sweet.TV", _t(M.FAV_REMOVED))
        xbmc.executebuiltin("Container.Refresh")
    elif action == "fav_up":
        favourites.move(params.get("channel_id", [""])[0], -1)
        xbmc.executebuiltin("Container.Refresh")
    elif action == "fav_down":
        favourites.move(params.get("channel_id", [""])[0], 1)
        xbmc.executebuiltin("Container.Refresh")
    else:
        _log("Unknown action: %s" % action, level=xbmc.LOGWARNING)
        show_main_menu(handle)


# -- Main menu -----------------------------------------------------------


def show_main_menu(handle):
    """Show the addon's main navigation menu."""
    items = [
        (_t(M.LIVE_TV), "browse_channels", "DefaultTVShows.png", True),
        (_t(M.ARCHIVE), "browse_archive", "DefaultYear.png", True),
        (_t(M.MOVIES), "browse_movies", "DefaultMovies.png", True),
        (_t(M.SEARCH), "search", "DefaultAddonsSearch.png", True),
        (_t(M.REGISTERED_DEVICES), "manage_devices", "DefaultNetwork.png", True),
        (_t(M.SUBSCRIPTION_TITLE), "subscription_info", "DefaultIconInfo.png", False),
        (_t(M.OPEN_SETTINGS), "open_settings", "DefaultAddonService.png", False),
    ]

    for label, action, icon, is_folder in items:
        url = "plugin://plugin.video.sweettv/?action=%s" % action
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": icon})
        if not is_folder:
            li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle)


# -- Live TV channel list ------------------------------------------------


def browse_channels(handle, params=None):
    """Show channel categories, or channels within a category."""
    if params is None:
        params = {}

    category_id = params.get("category_id", [None])[0]

    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.NOT_LOGGED_IN))
        return

    # Prompt for adult PIN once per session if needed.
    _maybe_prompt_adult_pin()

    addon = xbmcaddon.Addon()
    show_adult = show_adult_allowed()
    channels, categories = api.get_channels()
    fav_ids = favourites.load()

    # If no category selected, show category list.
    if category_id is None:
        # Inject Favourites at the top if user has any.
        if fav_ids:
            url = "plugin://plugin.video.sweettv/?action=browse_channels&category_id=favourites"
            li = xbmcgui.ListItem(_t(M.FAVOURITES))
            li.setArt({"icon": "DefaultFavourites.png"})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        for cat in categories:
            # Skip adult category if disabled.
            if not show_adult and cat["id"] == 1:
                continue
            # Skip empty categories - the sweet.tv API doesn't expose
            # favourites via this endpoint, so the Favourite category
            # is always empty here.
            if not cat["channel_list"]:
                continue
            url = "plugin://plugin.video.sweettv/?action=browse_channels&category_id=%s" % cat["id"]
            li = xbmcgui.ListItem(cat["name"])
            li.setArt({"icon": cat.get("icon_url") or "DefaultTVShows.png"})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        xbmcplugin.endOfDirectory(handle)
        return

    # Filter channels by category.
    if category_id == "favourites":
        ch_by_id = {ch["id"]: ch for ch in channels}
        channels = [ch_by_id[fid] for fid in fav_ids if fid in ch_by_id]
    else:
        cat_id = int(category_id)
        selected_cat = next((c for c in categories if c["id"] == cat_id), None)
        if selected_cat and selected_cat["channel_list"]:
            ch_by_id = {int(ch["id"]): ch for ch in channels}
            channels = [ch_by_id[cid] for cid in selected_cat["channel_list"] if cid in ch_by_id]
        else:
            channels = []

    # Get current EPG for channel descriptions.
    channel_ids = [int(ch["id"]) for ch in channels]
    epg = api.get_epg(limit_next=1, channels=channel_ids) if channel_ids else {}

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

        # Context menu: pin/unpin and (in Pinned view) reorder.
        ctx_items = []
        if ch["id"] in fav_ids:
            unpin_url = "plugin://plugin.video.sweettv/?action=fav_remove&channel_id=%s" % ch["id"]
            ctx_items.append((_t(M.FAV_REMOVE), "RunPlugin(%s)" % unpin_url))
            if category_id == "favourites":
                up_url = "plugin://plugin.video.sweettv/?action=fav_up&channel_id=%s" % ch["id"]
                down_url = "plugin://plugin.video.sweettv/?action=fav_down&channel_id=%s" % ch["id"]
                ctx_items.append((_t(M.FAV_MOVE_UP), "RunPlugin(%s)" % up_url))
                ctx_items.append((_t(M.FAV_MOVE_DOWN), "RunPlugin(%s)" % down_url))
        else:
            pin_url = "plugin://plugin.video.sweettv/?action=fav_add&channel_id=%s" % ch["id"]
            ctx_items.append((_t(M.FAV_ADD), "RunPlugin(%s)" % pin_url))
        li.addContextMenuItems(ctx_items)

        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)


# -- Live TV playback ----------------------------------------------------


def play_channel(handle, params):
    """Play a live TV channel."""
    channel_id = params.get("channel_id", [None])[0]
    _vlog("play_channel called channel_id=%s" % channel_id)
    if not channel_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.NOT_LOGGED_IN))
        return

    addon = xbmcaddon.Addon()
    max_bitrate_str = addon.getSetting("max_bitrate")
    max_bitrate = _parse_bitrate(max_bitrate_str)
    _vlog("play_channel: max_bitrate setting=%r parsed=%s" % (max_bitrate_str, max_bitrate))

    # Resolve to a specific variant - the master playlist contains an ad
    # preroll from ads-badtest.sweet.tv that's unreachable, so we pick a
    # variant directly which serves the actual stream.
    stream_url, stream_id = api.get_live_link(channel_id, max_bitrate=max_bitrate)
    _vlog("play_channel: get_live_link returned url=%s stream_id=%s" % (stream_url, stream_id))
    if not stream_url:
        xbmcgui.Dialog().notification("Sweet.TV", "Failed to load stream", xbmcgui.NOTIFICATION_ERROR)
        return

    # Append User-Agent as URL header (works with Kodi's built-in player).
    play_url = stream_url + "|User-Agent=" + SweetTVApi.USER_AGENT
    li = xbmcgui.ListItem(path=play_url)
    li.setMimeType("application/vnd.apple.mpegurl")
    li.setContentLookup(False)

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
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.NOT_LOGGED_IN))
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

    play_url = stream_url + "|User-Agent=" + SweetTVApi.USER_AGENT
    li = xbmcgui.ListItem(path=play_url)
    li.setMimeType("application/vnd.apple.mpegurl")
    li.setContentLookup(False)

    if stream_id:
        li.setProperty("sweettv_stream_id", str(stream_id))

    xbmcplugin.setResolvedUrl(handle, True, li)


# -- Archive browsing ----------------------------------------------------


def browse_archive(handle, params):
    """Show archive channel categories or channels with archive support."""
    category_id = params.get("category_id", [None])[0]

    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.NOT_LOGGED_IN))
        return

    _maybe_prompt_adult_pin()

    show_adult = show_adult_allowed()
    channels, categories = api.get_channels()
    fav_ids = favourites.load()

    # Filter to channels with catchup support only.
    catchup_channels = [
        ch for ch in channels
        if ch["catchup_days"] > 0 and (show_adult or not ch["adult"])
    ]
    catchup_ids = {ch["id"] for ch in catchup_channels}

    # If no category selected, show category list.
    if category_id is None:
        # Pinned channels that have catchup.
        pinned_with_catchup = [fid for fid in fav_ids if fid in catchup_ids]
        if pinned_with_catchup:
            url = "plugin://plugin.video.sweettv/?action=browse_archive&category_id=favourites"
            li = xbmcgui.ListItem(_t(M.FAVOURITES))
            li.setArt({"icon": "DefaultFavourites.png"})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # All channels with catchup.
        url = "plugin://plugin.video.sweettv/?action=browse_archive&category_id=all"
        li = xbmcgui.ListItem(_t(M.ARCHIVE_ALL))
        li.setArt({"icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        for cat in categories:
            if not show_adult and cat["id"] == 1:
                continue
            if not cat["channel_list"]:
                continue
            # Skip categories with no catchup channels.
            cat_catchup_count = sum(
                1 for cid in cat["channel_list"] if str(cid) in catchup_ids
            )
            if cat_catchup_count == 0:
                continue
            url = "plugin://plugin.video.sweettv/?action=browse_archive&category_id=%s" % cat["id"]
            li = xbmcgui.ListItem(cat["name"])
            li.setArt({"icon": cat.get("icon_url") or "DefaultTVShows.png"})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        xbmcplugin.endOfDirectory(handle)
        return

    # Category selected — list channels in it that have catchup.
    if category_id == "favourites":
        ch_by_id = {ch["id"]: ch for ch in catchup_channels}
        listed_channels = [ch_by_id[fid] for fid in fav_ids if fid in ch_by_id]
    elif category_id == "all":
        listed_channels = catchup_channels
    else:
        cat_id = int(category_id)
        selected_cat = next((c for c in categories if c["id"] == cat_id), None)
        if selected_cat and selected_cat["channel_list"]:
            ch_by_id = {int(ch["id"]): ch for ch in catchup_channels}
            listed_channels = [
                ch_by_id[cid] for cid in selected_cat["channel_list"] if cid in ch_by_id
            ]
        else:
            listed_channels = []

    for ch in listed_channels:
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
        # Kodi built-in weekday string IDs: Monday=11, Sunday=17.
        # Python weekday(): Monday=0, Sunday=6 -> map to 11..17.
        for i in range(catchup_days):
            day = now - timedelta(days=i)
            if i == 0:
                day_name = _t(M.TODAY)
            elif i == 1:
                day_name = _t(M.YESTERDAY)
            else:
                day_name = xbmc.getLocalizedString(11 + day.weekday())
            label = "%s — %s" % (day_name, day.strftime("%d.%m.%Y"))

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
    _vlog("browse_movies called with cat=%s" % cat)

    if cat is None:
        for label, cat_id in [(_t(M.BY_GENRE), "genres"), (_t(M.BY_COLLECTION), "collections")]:
            url = "plugin://plugin.video.sweettv/?action=browse_movies&cat=%s" % cat_id
            li = xbmcgui.ListItem(label)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        xbmcplugin.endOfDirectory(handle)
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        _log("browse_movies: not logged in", level=xbmc.LOGWARNING)
        return

    _vlog("browse_movies: fetching movie configuration")
    config = api.get_movie_configuration()
    if not config:
        _log("browse_movies: get_movie_configuration returned None", level=xbmc.LOGERROR)
        return

    _vlog("browse_movies: config keys=%s" % list(config.keys()))

    if cat == "genres":
        genres = config.get("genres", [])
        _vlog("browse_movies: %d genres found" % len(genres))
        if genres:
            _vlog("browse_movies: first genre sample=%s" % genres[0])
        for genre in genres:
            gid = genre.get("id")
            gtitle = genre.get("title") or genre.get("name") or genre.get("caption") or str(gid)
            url = "plugin://plugin.video.sweettv/?action=movie_genre&genre_id=%s" % gid
            li = xbmcgui.ListItem(gtitle)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    elif cat == "collections":
        builtin = config.get("collections", [])
        user_collections = api.get_movie_collections()
        _vlog("browse_movies: %d builtin collections, %d user collections" % (len(builtin), len(user_collections)))
        if builtin:
            _vlog("browse_movies: first builtin sample=%s" % builtin[0])
        if user_collections:
            _vlog("browse_movies: first user collection sample=%s" % user_collections[0])
        for col in builtin + user_collections:
            cid = col.get("id")
            ctitle = col.get("title") or col.get("name") or col.get("caption") or str(cid)
            url = "plugin://plugin.video.sweettv/?action=movie_collection&collection_id=%s" % cid
            li = xbmcgui.ListItem(ctitle)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle)


def movie_genre(handle, params):
    """Show movies in a genre."""
    genre_id = params.get("genre_id", [None])[0]
    _vlog("movie_genre called with genre_id=%s" % genre_id)
    if not genre_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        _log("movie_genre: not logged in", level=xbmc.LOGWARNING)
        return

    movies = api.get_movie_genre(genre_id)
    _vlog("movie_genre: %d movies returned" % len(movies))
    _list_movies(handle, movies)


def movie_collection(handle, params):
    """Show movies in a collection."""
    collection_id = params.get("collection_id", [None])[0]
    _vlog("movie_collection called with collection_id=%s" % collection_id)
    if not collection_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        _log("movie_collection: not logged in", level=xbmc.LOGWARNING)
        return

    movies = api.get_movie_collection(collection_id)
    _vlog("movie_collection: %d movies returned" % len(movies))
    _list_movies(handle, movies)


def play_movie(handle, params):
    """Play a movie."""
    movie_id = params.get("movie_id", [None])[0]
    owner_id = params.get("owner_id", [None])[0]
    _vlog("play_movie called movie_id=%s owner_id=%s" % (movie_id, owner_id))
    if not movie_id or not owner_id:
        _log("play_movie: missing movie_id or owner_id, params=%s" % params, level=xbmc.LOGERROR)
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        _log("play_movie: not logged in", level=xbmc.LOGERROR)
        return

    url, link_type = api.get_movie_link(movie_id, owner_id)
    _vlog("play_movie: GetLink returned url=%s link_type=%s" % (url, link_type))
    if not url:
        xbmcgui.Dialog().notification(
            "Sweet.TV",
            "Movie not in your subscription",
            xbmcgui.NOTIFICATION_WARNING,
        )
        # Tell Kodi the resolve failed so it stops the playlist iteration.
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    play_url = url + "|User-Agent=" + SweetTVApi.USER_AGENT
    li = xbmcgui.ListItem(path=play_url)
    if link_type == "DASH":
        li.setMimeType("application/dash+xml")
    else:
        li.setMimeType("application/vnd.apple.mpegurl")
    li.setContentLookup(False)

    xbmcplugin.setResolvedUrl(handle, True, li)


def _list_movies(handle, movies):
    """Add movie items to the directory listing.

    Only AVOD (free with ads) movies are playable - they're streamed as
    catchup events on a TV channel via OpenStream. Paid SVOD/TVOD movies
    use Widevine-protected DASH which we don't support.
    """
    for movie in movies:
        # Filter to AVOD only - paid SVOD/TVOD movies use Widevine DASH
        # which we don't support. The channel_id/epg_id needed for playback
        # is fetched per-movie at click time (not in this bulk listing).
        if movie.get("accessibility_model") != "ACCESSIBILITY_MODEL_AVOD":
            continue

        title = movie["title"]

        # Append year / rating as grey suffix.
        suffix_bits = []
        if movie.get("year"):
            suffix_bits.append("[%s]" % movie["year"])
        if movie.get("rating"):
            suffix_bits.append("★%s" % movie["rating"])
        if suffix_bits:
            title = "%s [COLOR gray]%s[/COLOR]" % (title, " ".join(suffix_bits))

        url = (
            "plugin://plugin.video.sweettv/"
            "?action=play_movie&movie_id=%s&owner_id=%s"
            % (movie["id"], movie["owner_id"])
        )
        li = xbmcgui.ListItem(title)
        # Use the decorated title (with year/rating suffix) so Kodi shows
        # it in views that pull from info.title rather than the ListItem
        # label. SortTitle is the bare title so alphabetical sort works.
        info = {"title": title, "sorttitle": movie["title"]}
        if movie.get("year"):
            info["year"] = movie["year"]
        if movie.get("rating"):
            info["rating"] = float(movie["rating"])
        li.setInfo("video", info)
        if movie.get("poster"):
            li.setArt({"poster": movie["poster"], "thumb": movie["poster"]})
        li.setProperty("IsPlayable", "true")

        # Context menu: show full details (description etc.) on demand.
        # Bulk GetMovieInfo doesn't return description, so we fetch it
        # lazily via a single-movie call when the user explicitly asks.
        info_url = (
            "plugin://plugin.video.sweettv/"
            "?action=movie_info&movie_id=%s" % movie["id"]
        )
        li.addContextMenuItems([
            (_t(M.MOVIE_INFO), "RunPlugin(%s)" % info_url),
        ])

        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.setContent(handle, "movies")
    # Offer sort methods - VIDEO_SORT_TITLE_IGNORE_THE uses info.sorttitle
    # (the bare title) so the [year] suffix doesn't affect ordering.
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.endOfDirectory(handle)


def show_movie_info(params):
    """Fetch single-movie info and show full details in a textviewer dialog."""
    movie_id = params.get("movie_id", [None])[0]
    if not movie_id:
        return

    api = SweetTVApi()
    if not api.is_logged_in():
        return

    movies = api.get_movie_info([int(movie_id)])
    if not movies:
        xbmcgui.Dialog().notification("Sweet.TV", _t(M.MOVIE_FAILED), xbmcgui.NOTIFICATION_ERROR)
        return

    m = movies[0]
    lines = []
    if m.get("title"):
        lines.append(m["title"])
        lines.append("")

    meta_bits = []
    if m.get("year"):
        meta_bits.append(str(m["year"]))
    if m.get("duration"):
        meta_bits.append("%d min" % (m["duration"] // 60))
    if m.get("rating"):
        meta_bits.append("IMDB %s" % m["rating"])
    if meta_bits:
        lines.append("  •  ".join(meta_bits))
        lines.append("")

    if m.get("plot"):
        lines.append(m["plot"])

    xbmcgui.Dialog().textviewer(m.get("title", "Sweet.TV"), "\n".join(lines))


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
        if not xbmcgui.Dialog().yesno("Sweet.TV", _t(M.PAIR_ALREADY)):
            return
        api.logout()

    code = api.get_signin_code()
    if not code:
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.PAIR_FAILED_CODE))
        return

    dialog = xbmcgui.DialogProgress()
    dialog.create(_t(M.PAIR_TITLE), _t(M.PAIR_INSTRUCTIONS).replace("{code}", code))

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
            xbmcgui.Dialog().ok("Sweet.TV", _t(M.PAIR_SUCCESS))
            return

        xbmc.sleep(interval * 1000)
        elapsed += interval

    dialog.close()
    xbmcgui.Dialog().ok("Sweet.TV", _t(M.PAIR_TIMEOUT))


def unpair_device():
    """Logout and clear credentials."""
    if not xbmcgui.Dialog().yesno("Sweet.TV", _t(M.UNPAIR_CONFIRM)):
        return

    api = SweetTVApi()
    api.logout()
    xbmcgui.Dialog().ok("Sweet.TV", _t(M.UNPAIR_SUCCESS))


# -- Device management ---------------------------------------------------


def manage_devices(handle):
    """Show list of registered devices."""
    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.NOT_LOGGED_IN))
        return

    devices = api.get_devices()
    if not devices:
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.NO_DEVICES))
        return

    from datetime import datetime

    # Identify "this device": the one with our exact model string and the
    # most recent date_added (in case of multiple matches from re-pairings).
    this_model = SweetTVApi._device_model()
    this_token = None
    candidates = [
        d for d in devices if (d.get("model") or "").strip() == this_model
    ]
    if candidates:
        candidates.sort(key=lambda d: int(d.get("date_added", 0)), reverse=True)
        this_token = candidates[0].get("token_id")

    for dev in devices:
        date_str = datetime.fromtimestamp(int(dev.get("date_added", 0))).strftime("%d.%m.%Y %H:%M")
        # Build a friendly device label: prefer model, fall back to subtype/type.
        model = (dev.get("model") or "").strip()
        subtype = (dev.get("subtype") or "").strip()
        dtype = (dev.get("type") or "").strip()
        if model:
            name = "%s (%s)" % (model, dtype) if dtype else model
        elif subtype and subtype != "Unknown":
            name = "%s (%s)" % (subtype, dtype) if dtype else subtype
        else:
            name = dtype or "?"
        is_this = dev.get("token_id") == this_token
        if is_this:
            label = "[B]%s %s[/B] — %s: %s" % (
                name, _t(M.SUB_THIS_DEVICE), _t(M.SUB_DEVICE_ADDED), date_str,
            )
        else:
            label = "%s — %s: %s" % (name, _t(M.SUB_DEVICE_ADDED), date_str)
        url = (
            "plugin://plugin.video.sweettv/"
            "?action=remove_device&token_id=%s" % dev.get("token_id", "")
        )
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": "DefaultNetwork.png", "thumb": "DefaultNetwork.png"})
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.setContent(handle, "files")
    xbmcplugin.endOfDirectory(handle)


def remove_device(params):
    """Remove a registered device."""
    token_id = params.get("token_id", [None])[0]
    if not token_id:
        return

    if not xbmcgui.Dialog().yesno("Sweet.TV", _t(M.REMOVE_DEVICE_CONFIRM)):
        return

    api = SweetTVApi()
    api.remove_device(token_id)
    xbmcgui.Dialog().ok("Sweet.TV", _t(M.DEVICE_REMOVED))
    xbmc.executebuiltin("Container.Refresh")


# -- PVR Simple Client auto-config ---------------------------------------


def configure_pvr_simple():
    """Configure PVR IPTV Simple Client to read from IPTV Manager output.

    Edits pvr.iptvsimple's instance-settings-1.xml directly: sets the M3U
    and EPG paths to point at IPTV Manager's generated files, enables
    catchup, and renames the instance label to Sweet.TV. Then restarts
    PVR Simple Client via JSON-RPC so the changes take effect.
    """
    import json
    import re

    # Check that PVR Simple Client is installed.
    try:
        xbmcaddon.Addon("pvr.iptvsimple")
    except RuntimeError:
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.PVR_NOT_INSTALLED))
        return

    settings_path = xbmcvfs.translatePath(
        "special://userdata/addon_data/pvr.iptvsimple/instance-settings-1.xml"
    )

    if not os.path.exists(settings_path):
        # PVR Simple has never been opened, so no instance file exists.
        # Open its settings once to create the instance, then retry.
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.PVR_NOT_CONFIGURED))
        xbmc.executebuiltin("Addon.OpenSettings(pvr.iptvsimple)")
        return

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        _log("configure_pvr_simple: read failed: %s" % e, level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Sweet.TV", str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    # In-place updates to the XML using regex (the file is small and
    # the format is consistent, no need for a full XML parser).
    # The instance label (kodi_addon_instance_name) lives in this same
    # file, not in a separate instance-N.xml as I first thought.
    updates = {
        "m3uPathType": "0",
        "m3uPath": "special://userdata/addon_data/service.iptv.manager/playlist.m3u8",
        "epgPathType": "0",
        "epgPath": "special://userdata/addon_data/service.iptv.manager/epg.xml",
        "catchupEnabled": "true",
        "kodi_addon_instance_name": "Sweet.TV",
    }

    new_content = content
    for key, value in updates.items():
        # Match either <setting id="X" default="true">old</setting>
        # or       <setting id="X">old</setting>
        # or       <setting id="X" default="true" /> (empty)
        pattern_full = re.compile(
            r'<setting id="%s"(?:\s+default="[^"]*")?[^/>]*>[^<]*</setting>' % re.escape(key)
        )
        pattern_empty = re.compile(
            r'<setting id="%s"(?:\s+default="[^"]*")?\s*/>' % re.escape(key)
        )
        replacement = '<setting id="%s">%s</setting>' % (key, value)
        if pattern_full.search(new_content):
            new_content = pattern_full.sub(replacement, new_content, count=1)
        elif pattern_empty.search(new_content):
            new_content = pattern_empty.sub(replacement, new_content, count=1)
        else:
            # Setting not present in file. Insert it before </settings>.
            new_content = new_content.replace(
                "</settings>", "    " + replacement + "\n</settings>", 1
            )

    settings_changed = (new_content != content)
    if settings_changed:
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except OSError as e:
            _log("configure_pvr_simple: write failed: %s" % e, level=xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Sweet.TV", str(e), xbmcgui.NOTIFICATION_ERROR)
            return
        _vlog("PVR Simple Client instance settings updated")
    else:
        _vlog("PVR Simple Client instance settings already correct, no changes")

    # Restart PVR Simple Client only if its instance settings actually
    # changed. The disable->enable cycle is racy when the addon is in
    # the middle of loading EPG, and re-running the action with no
    # changes shouldn't cycle the PVR client every time.
    if settings_changed:
        def _rpc(method, params):
            xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1,
            }))

        _rpc("Addons.SetAddonEnabled", {"addonid": "pvr.iptvsimple", "enabled": False})
        # Wait long enough for the addon's destruction to fully complete.
        # 500ms wasn't enough on Android TV - PVR Simple ended up in
        # "Permanent failure" state because the recreate raced the destroy.
        xbmc.sleep(2500)
        _rpc("Addons.SetAddonEnabled", {"addonid": "pvr.iptvsimple", "enabled": True})

    xbmcgui.Dialog().ok("Sweet.TV", _t(M.PVR_CONFIGURED))


# -- Kodi favourites shortcuts --------------------------------------------


def add_kodi_favourite(params):
    """Add a Sweet.TV section shortcut to Kodi's Favourites menu.

    Uses Favourites.AddFavourite JSON-RPC with a custom thumbnail so the
    entry has an icon instead of the default star.
    """
    import json

    target = params.get("target", [None])[0]
    if not target:
        return

    # Map target to plugin URL, title, and icon.
    targets = {
        "archive": {
            "title": _t(M.ARCHIVE),
            "path": "plugin://plugin.video.sweettv/?action=browse_archive",
            "icon": "DefaultYear.png",
        },
        "movies": {
            "title": _t(M.MOVIES),
            "path": "plugin://plugin.video.sweettv/?action=browse_movies",
            "icon": "DefaultMovies.png",
        },
    }

    cfg = targets.get(target)
    if not cfg:
        return

    # Prefix with "Sweet.TV" so it's recognizable in the favourites list.
    title = "Sweet.TV: %s" % cfg["title"]

    # Check if this favourite already exists — if so, remove it instead.
    existing = xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Favourites.GetFavourites",
        "params": {"properties": ["windowparameter"]},
        "id": 1,
    }))
    already_exists = False
    try:
        favs = json.loads(existing).get("result", {}).get("favourites") or []
        for fav in favs:
            if fav.get("windowparameter") == cfg["path"]:
                already_exists = True
                break
    except (ValueError, TypeError):
        pass

    if already_exists:
        # Already in favourites — confirm removal.
        if not xbmcgui.Dialog().yesno("Sweet.TV", "%s %s" % (title, _t(M.KODI_FAV_ALREADY))):
            return
        # AddFavourite with the same title toggles it off.
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Favourites.AddFavourite",
            "params": {
                "title": title,
                "type": "window",
                "window": "videos",
                "windowparameter": cfg["path"],
                "thumbnail": cfg["icon"],
            },
            "id": 1,
        }))
        xbmcgui.Dialog().notification("Sweet.TV", "%s %s" % (title, _t(M.KODI_FAV_REMOVED)))
        return

    resp_str = xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Favourites.AddFavourite",
        "params": {
            "title": title,
            "type": "window",
            "window": "videos",
            "windowparameter": cfg["path"],
            "thumbnail": cfg["icon"],
        },
        "id": 1,
    }))

    try:
        resp = json.loads(resp_str)
        if "error" in resp:
            _log("add_kodi_favourite failed: %s" % resp, level=xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Sweet.TV", "Failed", xbmcgui.NOTIFICATION_ERROR)
            return
    except (ValueError, TypeError):
        pass

    xbmcgui.Dialog().notification("Sweet.TV", "%s %s" % (title, _t(M.KODI_FAV_ADDED)))


# -- One-shot full PVR setup ---------------------------------------------


def setup_pvr_integration():
    """Install IPTV Manager + PVR Simple Client, refresh, then configure.

    The full happy-path for a fresh install: trigger Kodi's installer for
    each missing addon, wait for them to appear, run an IPTV Manager
    refresh so the M3U/EPG files exist, then run our existing
    configure_pvr_simple() to point PVR Simple at those files.
    """
    import json

    if not xbmcgui.Dialog().yesno("Sweet.TV", _t(M.PVR_SETUP_CONFIRM)):
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Sweet.TV", _t(M.PVR_SETUP_INSTALLING))

    def get_addon_state(addon_id):
        """Return ('not_installed' | 'disabled' | 'enabled') for an addon.

        Uses JSON-RPC Addons.GetAddonDetails which works regardless of
        enabled state, unlike xbmcaddon.Addon() which raises for disabled.
        """
        resp_str = xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Addons.GetAddonDetails",
            "params": {"addonid": addon_id, "properties": ["enabled"]},
            "id": 1,
        }))
        try:
            resp = json.loads(resp_str)
        except (ValueError, TypeError):
            return "not_installed"
        if "error" in resp:
            return "not_installed"
        addon_info = (resp.get("result") or {}).get("addon") or {}
        if addon_info.get("enabled"):
            return "enabled"
        return "disabled"

    def enable_addon(addon_id):
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Addons.SetAddonEnabled",
            "params": {"addonid": addon_id, "enabled": True},
            "id": 1,
        }))

    def wait_for(addon_id, timeout=120):
        """Make sure addon is installed AND enabled. Trigger install if needed."""
        state = get_addon_state(addon_id)
        if state == "enabled":
            return True
        if state == "disabled":
            enable_addon(addon_id)
            return True

        # Not installed - trigger Kodi's installer.
        progress.update(0, _t(M.PVR_SETUP_INSTALLING) + "\n" + addon_id)
        xbmc.executebuiltin("InstallAddon(%s)" % addon_id, wait=False)
        elapsed = 0
        step = 2
        while elapsed < timeout:
            if progress.iscanceled():
                return False
            xbmc.sleep(step * 1000)
            elapsed += step
            state = get_addon_state(addon_id)
            if state in ("enabled", "disabled"):
                if state == "disabled":
                    enable_addon(addon_id)
                return True
            progress.update(int(elapsed / timeout * 100))
        return False

    # Step 1: IPTV Manager.
    if not wait_for("service.iptv.manager"):
        progress.close()
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.PVR_SETUP_INSTALL_FAILED).format(addon="service.iptv.manager"))
        return

    # Step 2: PVR Simple Client.
    if not wait_for("pvr.iptvsimple"):
        progress.close()
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.PVR_SETUP_INSTALL_FAILED).format(addon="pvr.iptvsimple"))
        return

    # Step 3: trigger IPTV Manager refresh and wait for the M3U file.
    progress.update(0, _t(M.PVR_SETUP_REFRESHING))
    xbmc.executebuiltin("RunScript(service.iptv.manager,refresh)", wait=False)

    m3u_path = xbmcvfs.translatePath(
        "special://userdata/addon_data/service.iptv.manager/playlist.m3u8"
    )
    elapsed = 0
    timeout = 120
    while elapsed < timeout:
        if progress.iscanceled():
            progress.close()
            return
        if os.path.exists(m3u_path) and os.path.getsize(m3u_path) > 0:
            break
        xbmc.sleep(2000)
        elapsed += 2
        progress.update(int(elapsed / timeout * 100))
    else:
        progress.close()
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.PVR_SETUP_REFRESH_FAILED))
        return

    # Step 4: configure PVR Simple to read the IPTV Manager output.
    progress.update(80, _t(M.PVR_SETUP_CONFIGURING))
    progress.close()
    configure_pvr_simple()


# -- Subscription info ---------------------------------------------------


def show_subscription_info():
    """Show subscription details in a dialog."""
    api = SweetTVApi()
    if not api.is_logged_in():
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.NOT_LOGGED_IN))
        return

    response = api.get_user_info()
    if response.get("status") != "OK":
        xbmcgui.Dialog().ok("Sweet.TV", _t(M.SUBSCRIPTION_FAILED))
        return

    # Real fields live under the "info" key.
    info = response.get("info", {})
    lines = []

    # Account status.
    if info.get("is_blocked"):
        status = _t(M.SUB_STATUS_BLOCKED)
    elif info.get("account_status") == "ACTIVE":
        status = _t(M.SUB_STATUS_ACTIVE)
    else:
        status = info.get("account_status", "?")
    lines.append("%s: %s" % (_t(M.SUB_ACCOUNT), status))
    lines.append("")

    # Tariff / plan name.
    tariff = info.get("tariff", "")
    if tariff:
        lines.append("%s: %s" % (_t(M.SUB_PLAN), tariff))

    # Active services with expiry and days remaining.
    services = info.get("services") or []
    if services:
        lines.append("")
        lines.append("%s:" % _t(M.SUB_ACTIVE_SERVICES))
        from datetime import datetime, date
        today = date.today()
        for svc in services:
            name = svc.get("name", "?")
            expires_at = svc.get("expires_at", "")
            line = "  - %s" % name
            if expires_at:
                try:
                    exp_date = datetime.strptime(expires_at, "%Y-%m-%d").date()
                    days_left = (exp_date - today).days
                    line += " (%s %s, %d %s)" % (
                        _t(M.SUB_EXPIRES), expires_at, days_left, _t(M.SUB_DAYS_LEFT)
                    )
                except ValueError:
                    line += " (%s %s)" % (_t(M.SUB_EXPIRES), expires_at)
            lines.append(line)

    # Balance and amount due.
    balance = info.get("balance")
    to_pay = info.get("to_pay")
    if balance is not None:
        lines.append("")
        lines.append("%s: %s" % (_t(M.SUB_BALANCE), balance))
    if to_pay:
        lines.append("%s: %s" % (_t(M.SUB_TO_PAY), to_pay))

    # Parental control state.
    if info.get("parental_control_enabled"):
        lines.append("")
        lines.append("%s: %s" % (_t(M.SUB_PARENTAL_CONTROL), _t(M.SUB_ENABLED)))

    xbmcgui.Dialog().textviewer(_t(M.SUBSCRIPTION_TITLE), "\n".join(lines))


# -- Helpers -------------------------------------------------------------


def _maybe_prompt_adult_pin():
    """Prompt for the adult PIN if show_adult is on, a PIN is set, and the
    user hasn't already unlocked this session.

    Wrong PIN or cancel leaves the session locked - the user just sees
    the addon without adult channels (no error, no scolding).
    """
    addon = xbmcaddon.Addon()
    if not addon.getSettingBool("show_adult"):
        return
    pin = (addon.getSetting("adult_pin") or "").strip()
    if not pin:
        return
    if is_adult_unlocked():
        return

    entered = xbmcgui.Dialog().input(
        _t(M.ADULT_PIN_PROMPT),
        type=xbmcgui.INPUT_NUMERIC,
        option=xbmcgui.ALPHANUM_HIDE_INPUT,
    )
    if entered and entered == pin:
        set_adult_unlocked(True)


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
