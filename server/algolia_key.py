"""
algolia_key.py
==============
Purpose
-------
Fragrantica's search bar is powered by Algolia, a hosted search service. To turn
a plain name like "Aventus" into a real Fragrantica page URL, we call Algolia
directly, the same way Fragrantica's own website does.

Algolia requires an API key with every request. Fragrantica uses a "secured"
search-only key that EXPIRES (the expiry time is encoded inside the key). When
it expires, searches fail with HTTP 403 and the whole lookup chain breaks.

This module hides that problem from the rest of the server:
  * It remembers the current key (in memory, and in a file so it survives restarts).
  * It checks the key's expiry date before using it.
  * If the key is expired or rejected, it tries to find a fresh one automatically
    by scanning Fragrantica's pages and scripts for key-shaped strings, testing
    each against Algolia, and keeping the first one that works.

Public API (what other files should use)
----------------------------------------
    algolia_search(query, hits=1)  -> list of result dicts ("hits") from Algolia
    refresh_key()                  -> tries to find a working key, returns it or None

How to test this file alone
---------------------------
    python algolia_key.py
It prints the current key's expiry, whether it works, and whether an
auto-refresh found a new key.

Known limitation
----------------
Auto-refresh only works if Fragrantica puts the key inside its page HTML or
script files. If the site loads the key through a separate network request after
the page loads, the scan finds nothing, and you must copy a key by hand:
DevTools (F12) -> Network tab -> use the site's search box -> click the request
to algolia.net -> copy the value of the "x-algolia-api-key" header ->
paste it into algolia_key.txt (or into FALLBACK_KEY below).
"""

import base64   # secured Algolia keys are base64 text; we decode them to read the expiry
import os       # used to build the path of the key file next to this script
import re       # regular expressions, used to find key-shaped strings in web pages
import time     # used to compare the key's expiry timestamp with the current time
from urllib.parse import urljoin   # turns relative script URLs ("/js/a.js") into full URLs

import cloudscraper   # like the requests library, but gets past Cloudflare bot protection

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Algolia application ID. This identifies Fragrantica's account on Algolia.
# It does not expire. Found in the same DevTools request as the key.
APP_ID = "FGVI612DFZ"

# Name of the Algolia "index" (dataset) holding Fragrantica's perfumes.
# Other indexes exist (designers, articles); we only want perfumes.
INDEX = "fragrantica_perfumes"

# Algolia's search endpoint host. The app ID is part of the hostname, lowercased.
# "-dsn" is Algolia's fast, geographically distributed search endpoint.
HOST = "https://fgvi612dfz-dsn.algolia.net"

# Where a working key is saved so it survives server restarts.
# os.path.abspath(__file__) is this script's own location, so the file always
# lands next to algolia_key.py no matter which folder you run Python from.
KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algolia_key.txt")

# Used only if algolia_key.txt doesn't exist yet. Paste the long key that was
# originally in app.py here (the one starting with "YzZl..."). It is expected
# to be expired by now; it just gives the module a starting point.
FALLBACK_KEY = "PASTE_YOUR_OLD_KEY_HERE"

# Pages that are scanned for a fresh key during a refresh. The home page and the
# search page both load Fragrantica's search code.
PAGES = ["https://www.fragrantica.com/", "https://www.fragrantica.com/search/"]

# A cloudscraper session, created once and reused. It behaves like a browser
# closely enough to pass Fragrantica's Cloudflare protection, which plain
# requests calls get blocked by (HTTP 403).
_scraper = cloudscraper.create_scraper()

# The key currently in use, held in memory. None means "not loaded yet".
_key = None

# ---------------------------------------------------------------------------
# PATTERNS USED TO HUNT FOR A KEY INSIDE WEB PAGES
# ---------------------------------------------------------------------------

# Pattern 1: any long run of base64-style characters (60+). Secured Algolia keys
# are long base64 strings, so this catches them wherever they appear. Matches
# are then filtered by _expiry(), which only accepts strings that decode to
# something containing "validUntil=" (the signature of a secured key).
KEY_SHAPED = re.compile(r"[A-Za-z0-9+/_\-]{60,}={0,2}")

# Pattern 2: a value that sits right after a label such as apiKey or
# x-algolia-api-key, e.g.  apiKey: "abc123..."  or  "x-algolia-api-key":"abc..."
# Catches keys that are not long/secured (e.g. a plain 32-character key).
# re.I = case-insensitive. The captured group (the part in parentheses) is the key.
LABELED = re.compile(
    r"""(?:apiKey|api_key|searchKey|x-algolia-api-key)["'\s:=]+["']?([A-Za-z0-9+/=_\-]{20,})""",
    re.I,
)

# ---------------------------------------------------------------------------
# KEY INSPECTION HELPERS
# ---------------------------------------------------------------------------


def _expiry(key):
    """
    Returns the key's expiry as a Unix timestamp (seconds since 1970), or None
    if the key doesn't carry one.

    Why this works: a secured Algolia key is base64 text. Decoded, it looks like
        <signature>validUntil=1791061921
    and that number is the moment the key stops working. Reading it lets us know
    a key is dead WITHOUT making a failing network request.
    """
    try:
        # base64 text must be a multiple of 4 characters long; "=" is padding.
        # -len(key) % 4 works out how many "=" characters are missing.
        decoded = base64.b64decode(key + "=" * (-len(key) % 4)).decode("latin-1")
    except Exception:
        return None   # not valid base64, so it is not a secured key

    m = re.search(r"validUntil=(\d+)", decoded)
    return int(m.group(1)) if m else None


def _is_fresh(key, margin=3600):
    """
    True if the key is still usable. "margin" treats a key as expired one hour
    (3600 seconds) early, so it is never used right as it dies mid-request.
    Keys with no expiry information are assumed fresh; the server will find out
    if they are rejected and then refresh.
    """
    exp = _expiry(key)
    return exp is None or exp > time.time() + margin


# ---------------------------------------------------------------------------
# TALKING TO ALGOLIA
# ---------------------------------------------------------------------------


def _post(key, query, hits):
    """
    Sends one search request to Algolia and returns the raw response object.

    The request body is the same shape Fragrantica's own search bar sends:
      indexName -> which dataset to search
      query     -> the text being searched for
      params    -> extra options; hitsPerPage=N limits how many results come back

    The key and app ID travel in HTTP headers, which is how Algolia authenticates.
    """
    return _scraper.post(
        HOST + "/1/indexes/*/queries",
        headers={"x-algolia-application-id": APP_ID, "x-algolia-api-key": key},
        json={"requests": [{"indexName": INDEX,
                            "query": query,
                            "params": f"hitsPerPage={hits}"}]},
        timeout=15,   # seconds; never hang forever if the network stalls
    )


def _works(key):
    """
    True if Algolia accepts this key. It runs a tiny real search ("aventus").
    Used to confirm that a candidate found by scanning is really a valid key,
    not just a random long string.
    """
    try:
        return _post(key, "aventus", 1).status_code == 200
    except Exception:
        return False   # network error counts as "doesn't work"


# ---------------------------------------------------------------------------
# SAVING AND LOADING THE KEY
# ---------------------------------------------------------------------------


def _save(key):
    """Writes the working key to algolia_key.txt so it survives a server restart."""
    with open(KEY_FILE, "w") as f:
        f.write(key)


def _read_file():
    """Returns the saved key from algolia_key.txt, or None if there isn't one."""
    try:
        with open(KEY_FILE) as f:
            return f.read().strip() or None   # empty file also counts as "none"
    except OSError:
        return None   # file doesn't exist yet (normal on the first run)


# ---------------------------------------------------------------------------
# AUTOMATIC KEY REFRESH
# ---------------------------------------------------------------------------


def refresh_key(verbose=False):
    """
    Hunts for a working Algolia key and returns it (also saving it to disk), or
    returns None if nothing worked.

    How it works:
      1. Download Fragrantica's home and search pages.
      2. Find the <script src="..."> files each page loads and download up to 25
         of them (keys often live in JavaScript files, not in the HTML itself).
      3. Search all that text for key-shaped strings using the two patterns above.
      4. Test every candidate against Algolia; keep the first that is accepted.

    verbose=True prints how many documents were scanned and candidates found,
    which is what tells you WHY a refresh failed when you run this file directly.
    """
    texts = []   # raw text of every page and script we manage to download

    for page in PAGES:
        try:
            r = _scraper.get(page, timeout=20)
        except Exception as e:
            print("algolia refresh: could not load", page, e)
            continue   # skip this page, try the next one

        if r.status_code != 200:
            print("algolia refresh:", page, "returned", r.status_code)
            continue

        texts.append(r.text)

        # Find every <script src="..."> on the page. The [:25] cap prevents a
        # page with hundreds of scripts from making the refresh take minutes.
        srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
        for src in srcs[:25]:
            url = urljoin(page, src)   # make relative links absolute
            # Only fetch Fragrantica's own scripts, not ads/analytics from others.
            if "fragrantica" in url or "fimgs" in url:
                try:
                    texts.append(_scraper.get(url, timeout=20).text)
                except Exception:
                    pass   # one unreachable script shouldn't abort the refresh

    # Collect candidate keys from everything we downloaded.
    candidates = []
    for text in texts:
        for c in KEY_SHAPED.findall(text):
            if _expiry(c) is not None:   # keep only strings that look like secured keys
                candidates.append(c)
        candidates.extend(LABELED.findall(text))

    # dict.fromkeys removes duplicates while keeping the original order.
    candidates = list(dict.fromkeys(candidates))

    if verbose:
        print(f"scanned {len(texts)} documents, found {len(candidates)} candidate keys")

    # The deciding test: does Algolia actually accept this candidate?
    for c in candidates:
        if _works(c):
            _save(c)
            return c

    return None   # nothing found; the caller must handle this


def get_key():
    """
    Returns a key that should work right now.

    Order of preference:
      1. The key already in memory.
      2. The key saved in algolia_key.txt.
      3. FALLBACK_KEY from this file.
    If the chosen key is expired, an automatic refresh is attempted first.
    """
    global _key   # we assign to the module-level variable, not a local copy

    if _key is None:
        _key = _read_file() or FALLBACK_KEY

    if not _is_fresh(_key):
        new = refresh_key()
        if new:
            _key = new   # use the fresh key; if refresh failed we keep the old one

    return _key


# ---------------------------------------------------------------------------
# THE FUNCTION THE REST OF THE SERVER USES
# ---------------------------------------------------------------------------


def algolia_search(query, hits=1):
    """
    Searches Fragrantica's perfume index and returns a list of hits.

    Each hit is a dictionary. The fields we rely on:
        "slug" -> e.g. "Creed/Aventus"  (brand/name, already URL-safe)
        "id"   -> e.g. 9828             (Fragrantica's numeric perfume ID)
    which combine into https://www.fragrantica.com/perfume/{slug}-{id}.html

    Self-healing behavior: if Algolia rejects the key (HTTP 400/401/403), this
    triggers ONE refresh attempt and retries once. If that also fails it raises
    RuntimeError, which app.py turns into a clear error message for the caller.
    """
    global _key

    for attempt in (1, 2):   # attempt 1 = normal try, attempt 2 = after a refresh
        r = _post(get_key(), query, hits)

        # Key rejected on the first try: refresh once, then loop around to retry.
        if r.status_code in (400, 401, 403) and attempt == 1:
            new = refresh_key()
            if new:
                _key = new
                continue   # jump to attempt 2 with the new key

        # Anything other than success at this point is a real failure.
        if r.status_code != 200:
            raise RuntimeError(f"Algolia key rejected ({r.status_code}) and auto-refresh failed")

        # Algolia wraps results in a list (you can query several indexes at once).
        # We sent one query, so we want results[0], then its "hits" list.
        return r.json()["results"][0]["hits"]


# ---------------------------------------------------------------------------
# SELF-TEST: run  "python algolia_key.py"  to diagnose key problems
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    k = get_key()
    exp = _expiry(k)
    print("current key expires:", time.ctime(exp) if exp else "unknown")
    print("current key works:", _works(k))
    new = refresh_key(verbose=True)
    print("refresh result:", "FOUND a working key" if new else "nothing found")