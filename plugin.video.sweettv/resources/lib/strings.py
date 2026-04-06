# -*- coding: utf-8 -*-
"""Localized string ID constants.

Maps human-readable names to the numeric IDs used in strings.po files.
Use the M (messages) namespace for everything: M.PAIR_TITLE, etc.

When adding new strings:
  1. Add an entry here with the next available ID in the right range.
  2. Add the English text to resources/language/.../en_gb/strings.po.
  3. Add translations to other language strings.po files.
"""

import xbmcaddon


class _MessageRegistry:
    """Holds string ID constants and resolves them to localized text."""

    # Main menu (30100-30199).
    LIVE_TV = 30100
    ARCHIVE = 30101
    MOVIES = 30102
    SEARCH = 30103
    FAVOURITES = 30104

    # Pairing (30200-30299).
    PAIR_DEVICE = 30200
    PAIR_TITLE = 30201
    PAIR_INSTRUCTIONS = 30202
    PAIR_ALREADY = 30203
    PAIR_FAILED_CODE = 30204
    PAIR_SUCCESS = 30205
    PAIR_TIMEOUT = 30206
    UNPAIR_CONFIRM = 30207
    UNPAIR_SUCCESS = 30208
    NOT_LOGGED_IN = 30209

    # Errors (30300-30399).
    STREAM_FAILED = 30300
    ARCHIVE_STREAM_FAILED = 30301
    MOVIE_FAILED = 30302

    # Favourites (30400-30499).
    FAV_ADD = 30400
    FAV_REMOVE = 30401
    FAV_ADDED = 30402
    FAV_REMOVED = 30403

    # Browse (30500-30599).
    SEARCH_PROMPT = 30500
    BY_GENRE = 30501
    BY_COLLECTION = 30502
    TODAY = 30503
    YESTERDAY = 30504

    # Device management (30600-30699).
    REGISTERED_DEVICES = 30600
    NO_DEVICES = 30601
    REMOVE_DEVICE_CONFIRM = 30602
    DEVICE_REMOVED = 30603
    SELECT_TO_REMOVE = 30604

    # Subscription (30700-30799).
    SUBSCRIPTION_TITLE = 30700
    SUBSCRIPTION_FAILED = 30701
    SUB_ACCOUNT = 30702
    SUB_PLAN = 30703
    SUB_ACTIVE_SERVICES = 30704
    SUB_EXPIRES = 30705
    SUB_DAYS_LEFT = 30706
    SUB_BALANCE = 30707
    SUB_TO_PAY = 30708
    SUB_PARENTAL_CONTROL = 30709
    SUB_ENABLED = 30710
    SUB_STATUS_ACTIVE = 30711
    SUB_STATUS_BLOCKED = 30712
    SUB_DEVICE_ADDED = 30713
    SUB_DEVICE_SELECT_REMOVE = 30714
    SUB_THIS_DEVICE = 30715
    OPEN_SETTINGS = 30716
    MOVIE_INFO = 30717

    # Settings labels (30800-30899) — these are referenced from settings.xml
    # by ID, no need to use them in Python code.

    @staticmethod
    def get(string_id):
        """Resolve a string ID to its localized text."""
        return xbmcaddon.Addon().getLocalizedString(string_id)


M = _MessageRegistry()


def t(name_or_id):
    """Get a localized string by attribute name or numeric ID.

    Examples:
        t(M.PAIR_TITLE)        # by ID via constant
        t("PAIR_TITLE")        # by name (string lookup)
    """
    if isinstance(name_or_id, int):
        return M.get(name_or_id)
    return M.get(getattr(M, name_or_id))
