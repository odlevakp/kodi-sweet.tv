# -*- coding: utf-8 -*-
"""Client-side favourites storage for Sweet.TV channels.

Stores a list of favourite channel IDs in a JSON file in the addon's
profile directory. Persists across addon restarts.
"""

import json
import os

import xbmcaddon
import xbmcvfs


def _favourites_file():
    """Path to the favourites JSON file."""
    addon = xbmcaddon.Addon()
    profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
    os.makedirs(profile, exist_ok=True)
    return os.path.join(profile, "favourites.json")


def load():
    """Return list of favourite channel IDs (as strings)."""
    try:
        with open(_favourites_file(), "r") as f:
            data = json.load(f)
            return [str(x) for x in data]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(channel_ids):
    """Save list of favourite channel IDs."""
    with open(_favourites_file(), "w") as f:
        json.dump([str(x) for x in channel_ids], f)


def add(channel_id):
    """Add a channel to favourites."""
    favs = load()
    cid = str(channel_id)
    if cid not in favs:
        favs.append(cid)
        save(favs)


def remove(channel_id):
    """Remove a channel from favourites."""
    favs = load()
    cid = str(channel_id)
    if cid in favs:
        favs.remove(cid)
        save(favs)


def is_favourite(channel_id):
    """Check if a channel is in favourites."""
    return str(channel_id) in load()


def move(channel_id, delta):
    """Move a pinned channel up (delta=-1) or down (delta=+1)."""
    favs = load()
    cid = str(channel_id)
    if cid not in favs:
        return
    idx = favs.index(cid)
    new_idx = idx + delta
    if new_idx < 0 or new_idx >= len(favs):
        return
    favs[idx], favs[new_idx] = favs[new_idx], favs[idx]
    save(favs)
