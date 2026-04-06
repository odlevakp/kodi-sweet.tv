# Localization

The Sweet.TV addon uses Kodi's standard `.po` localization system, with a thin Python wrapper that lets you reference strings by **name** instead of numeric ID.

## How It Works

```
plugin.video.sweettv/
├── addon.py                           ← uses _t(M.PAIR_TITLE) etc.
└── resources/
    ├── lib/
    │   └── strings.py                 ← defines M.PAIR_TITLE = 30201
    └── language/
        ├── resource.language.en_gb/
        │   └── strings.po             ← English text for ID 30201
        └── resource.language.sk_sk/
            └── strings.po             ← Slovak text for ID 30201
```

At runtime, `_t(M.PAIR_TITLE)` resolves to `xbmcaddon.Addon().getLocalizedString(30201)`, which Kodi translates to the user's UI language.

## Why Named Constants

Calling `_t(30201)` works but the number tells you nothing. With `_t(M.PAIR_TITLE)` the intent is obvious, IDE autocomplete works, and a typo becomes an `AttributeError` at import time instead of a silent missing string.

## ID Number Ranges

The numeric IDs are organized into ranges by topic. Settings IDs (30800-30899) are referenced from `settings.xml` directly and don't need Python constants.

| Range       | Topic                           |
|-------------|---------------------------------|
| 30100-30199 | Main menu items                 |
| 30200-30299 | Device pairing flow             |
| 30300-30399 | Errors                          |
| 30400-30499 | Favourites                      |
| 30500-30599 | Browse / search prompts         |
| 30600-30699 | Device management               |
| 30700-30799 | Subscription                    |
| 30800-30899 | Settings labels (settings.xml)  |

Kodi reserves IDs below 30000 for built-in strings. Stay above 30000.

## Adding a New String

1. **Pick the next ID** in the appropriate range (look in [strings.py](../plugin.video.sweettv/resources/lib/strings.py)).

2. **Add a constant** to [strings.py](../plugin.video.sweettv/resources/lib/strings.py):

   ```python
   class _MessageRegistry:
       # Errors (30300-30399).
       STREAM_FAILED = 30300
       MY_NEW_ERROR = 30303   # ← new
   ```

3. **Add the English text** to [resources/language/resource.language.en_gb/strings.po](../plugin.video.sweettv/resources/language/resource.language.en_gb/strings.po):

   ```po
   msgctxt "#30303"
   msgid "Something went wrong"
   msgstr ""
   ```

   Note: in `en_gb`, `msgstr` stays empty — Kodi falls back to `msgid` when no translation is provided.

4. **Add translations** to other language files (e.g. `sk_sk/strings.po`):

   ```po
   msgctxt "#30303"
   msgid "Something went wrong"
   msgstr "Niečo sa pokazilo"
   ```

5. **Use it in Python**:

   ```python
   from resources.lib.strings import M, t as _t

   xbmcgui.Dialog().ok("Sweet.TV", _t(M.MY_NEW_ERROR))
   ```

## Adding a New Language

1. Create `plugin.video.sweettv/resources/language/resource.language.<code>/` (e.g. `resource.language.cs_cz` for Czech).

2. Copy `strings.po` from the English directory and translate every `msgstr`. Keep the `msgctxt` and `msgid` lines unchanged.

3. Update the language metadata at the top of the new file:

   ```po
   "Language-Team: Czech\n"
   "Language: cs_CZ\n"
   ```

4. Test by switching Kodi's language: **Settings → Interface → Regional → Language**.

## String Substitution

For strings that need runtime values, use a placeholder in the `.po` file and replace it in Python:

```po
msgctxt "#30202"
msgid "Your pairing code is: [B]{code}[/B]..."
msgstr ""
```

```python
_t(M.PAIR_INSTRUCTIONS).replace("{code}", code)
```

Don't use Python's `%` or `.format()` directly on translated strings — Kodi's `.po` workflow doesn't preserve format specifiers reliably across translations. The `.replace()` approach with named placeholders is safer.

## Settings Labels

Settings UI labels live in [settings.xml](../plugin.video.sweettv/resources/settings.xml) and reference IDs directly:

```xml
<setting id="show_adult" type="bool" label="30805" default="false"/>
```

Where `30805` is defined in the `.po` files. No Python constant needed for these — they're never used from code.

## Validation

To check that every constant in `strings.py` has a corresponding entry in the English `.po`:

```bash
python3 -c "
import re
ids_in_code = set()
with open('plugin.video.sweettv/resources/lib/strings.py') as f:
    for line in f:
        m = re.match(r'\s+\w+\s*=\s*(\d+)', line)
        if m: ids_in_code.add(int(m.group(1)))

ids_in_po = set()
with open('plugin.video.sweettv/resources/language/resource.language.en_gb/strings.po') as f:
    for line in f:
        m = re.match(r'msgctxt \"#(\d+)\"', line)
        if m: ids_in_po.add(int(m.group(1)))

missing_in_po = ids_in_code - ids_in_po
unused_in_code = ids_in_po - ids_in_code
if missing_in_po: print('Missing in en_gb/strings.po:', sorted(missing_in_po))
if unused_in_code: print('Unused in code (settings labels OK):', sorted(unused_in_code))
if not missing_in_po and not unused_in_code: print('All good.')
"
```
