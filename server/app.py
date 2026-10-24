"""
app.py
======
A small web server (Flask) that the ESP32 fragrance stand talks to over WiFi.

What it does
------------
Given a fragrance name, it returns that fragrance's top notes and a few similar
("reminds me of") fragrances as JSON, by looking the fragrance up on Fragrantica.

Endpoint
--------
    GET /notes?name=<fragrance name>

    Success (HTTP 200):
        {"name": "Aventus", "notes": "Pineapple, Bergamot, Apple", "remindsMeOf": "A, B, C"}
    Not found or temporary scrape failure (HTTP 200, placeholder text):
        {"name": "...", "notes": "not found" | "unavailable", "remindsMeOf": "..."}
    Algolia key dead and auto-refresh failed (HTTP 503):
        {"name": "...", "error": "algolia key expired and auto-refresh failed"}
    Missing name (HTTP 400):
        {"error": "missing name"}

How a request flows
-------------------
    name -> Algolia search (algolia_key.py) -> real Fragrantica page URL
         -> download that page (cloudscraper, with retries)
         -> parse notes and similar fragrances out of the HTML (BeautifulSoup)
         -> JSON back to the caller

Running it
----------
    cd server
    venv\\Scripts\\activate        (Windows; the "(venv)" tag should appear)
    python app.py
Then open http://localhost:5000/notes?name=Aventus in a browser.
host="0.0.0.0" (bottom of file) lets other devices on the same WiFi, such as the
ESP32, reach the server using this computer's IP address.

Dependencies (pip install ...)
------------------------------
    flask cloudscraper beautifulsoup4 requests
"""

from flask import Flask, request, jsonify   # Flask = the web framework; request reads the
                                            # incoming URL; jsonify builds JSON responses
import cloudscraper                         # downloads pages while passing Cloudflare checks
import time                                 # used to pause between retry attempts
from bs4 import BeautifulSoup               # parses HTML so we can search it by class/tag

from algolia_key import algolia_search      # name -> search results; handles the Algolia key
                                            # (and refreshes it automatically when it expires)

# ---------------------------------------------------------------------------
# CACHE
# ---------------------------------------------------------------------------
# A dictionary kept in memory: lowercase fragrance name -> result dictionary.
# A repeat request for the same fragrance returns instantly without touching the
# internet. It is emptied whenever the server restarts, because it lives only in
# RAM. (A file-based cache would survive restarts; a possible future upgrade.)
# Only SUCCESSFUL lookups are stored; see get_notes() for why.
cache = {}


# ---------------------------------------------------------------------------
# STEP 1: FRAGRANCE NAME -> FRAGRANTICA PAGE URL
# ---------------------------------------------------------------------------
def find_fragrance_url(name):
    """
    Turns a plain name (e.g. "Meteore") into the real page URL, e.g.
    "https://www.fragrantica.com/perfume/Louis-Vuitton/Meteore-62251.html".

    Fragrantica URLs end in a numeric ID that can't be guessed from the name, so
    we ask Algolia (the search service behind Fragrantica's own search bar).

    Returns the URL string, or None if the search found nothing.
    May raise RuntimeError if the Algolia key is dead and couldn't be refreshed;
    scrap_notes() catches that.
    """
    hits = algolia_search(name, hits=1)   # hits=1: we only want the single best match

    # An empty list means Algolia found no perfume matching that name.
    if len(hits) == 0:
        return None

    first_hit = hits[0]

    # Algolia doesn't hand us a ready-made URL. We build it from two fields:
    #   slug -> "Louis-Vuitton/Meteore"  (brand and name, URL-safe already)
    #   id   -> 62251                    (Fragrantica's unique perfume number)
    slug = first_hit.get("slug")
    fragrance_id = first_hit.get("id")

    # If either piece is missing we can't build a valid URL, so give up cleanly.
    if slug is None or fragrance_id is None:
        return None

    # f-string: {slug} and {fragrance_id} are replaced with their values.
    return f"https://www.fragrantica.com/perfume/{slug}-{fragrance_id}.html"


# ---------------------------------------------------------------------------
# STEP 2: DOWNLOAD THE PAGE
# ---------------------------------------------------------------------------
def scrape_page_with_retry(url, max_attempts=3, delay_seconds=2):
    """
    Downloads a URL, retrying if the site blocks us.

    Fragrantica sits behind Cloudflare bot protection. A plain requests.get()
    gets HTTP 403. cloudscraper imitates a real browser well enough to pass most
    of the time, and the occasional rejection is usually temporary, so we wait a
    couple of seconds and try again.

    Returns the response object on success (HTTP 200), or None if every attempt
    failed.
    """
    scraper = cloudscraper.create_scraper()   # browser-like session object

    for attempt_number in range(1, max_attempts + 1):   # attempts numbered 1..max_attempts
        response = scraper.get(url)

        # HTTP 200 means "OK". Anything else is a failure or a block.
        if response.status_code == 200:
            return response

        # Log the failure to the server terminal, then pause before retrying so a
        # temporary block or rate limit has time to clear.
        print(f"Attempt {attempt_number} failed with status {response.status_code}, retrying...")
        time.sleep(delay_seconds)

    return None   # every attempt failed


# ---------------------------------------------------------------------------
# STEP 3: PARSE THE PAGE
# ---------------------------------------------------------------------------
def scrap_notes(name):
    """
    The main lookup. Runs the whole pipeline for one fragrance name and ALWAYS
    returns a dictionary, never crashing the server.

    Returns one of:
      {"name", "notes", "remindsMeOf"}  with real data on success,
      the same keys with "not found"    if Algolia found no matching perfume,
      the same keys with "unavailable"  if the page couldn't be downloaded or
                                        something unexpected broke,
      {"name", "error"}                 if the Algolia key is dead and the
                                        automatic refresh also failed.
    """
    try:
        # Step 1: name -> page URL.
        url = find_fragrance_url(name)
        if url is None:
            return {"name": name, "notes": "not found", "remindsMeOf": "not found"}

        # Step 2: download the page (with retries).
        response = scrape_page_with_retry(url)
        if response is None:
            return {"name": name, "notes": "unavailable", "remindsMeOf": "unavailable"}

        # BeautifulSoup converts the raw HTML text into a searchable tree, much
        # like a browser builds the page structure (the DOM).
        soup = BeautifulSoup(response.text, "html.parser")

        # --- NOTES ---
        # Each note (e.g. "Bergamot") on the page is an element with the CSS class
        # "pyramid-note-label". find_all returns every element with that class.
        # This is a list comprehension: for each element, take its visible text
        # (.text) with surrounding whitespace removed (.strip()).
        notes_list = [el.text.strip() for el in soup.find_all(class_="pyramid-note-label")]

        # Keep only the first 3: the display is small. [:3] means "the first 3 items".
        # ", ".join(...) turns ["A", "B", "C"] into the text "A, B, C".
        notes_string = ", ".join(notes_list[:3])

        # --- "REMINDS ME OF" ---
        # Each suggested fragrance is a "card" with the class
        # "tw-carousel-perfume-card". Inside a card is a link whose address looks like
        #   /perfume/Armaf/Club-de-Nuit-Intense-Man-34696.html
        # The readable name is hidden in the last part of that address.
        remind_list = []
        for card in soup.find_all(class_="tw-carousel-perfume-card"):
            a_tag = card.find("a")   # the link inside this card (None if absent)
            if a_tag:
                # split("/") breaks the address into pieces; [-1] is the last piece:
                # "Club-de-Nuit-Intense-Man-34696.html"
                last_part = a_tag.get("href").split("/")[-1]

                # Clean it into a readable name:
                name_part = last_part.replace(".html", "")   # drop the file extension
                name_part, _ = name_part.rsplit("-", 1)      # drop the trailing "-34696" ID
                                                             # (rsplit splits from the right,
                                                             # once; "_" discards the ID)
                remind_list.append(name_part.replace("-", " "))   # dashes -> spaces

        reminds_string = ", ".join(remind_list[:3])   # first 3 only, same display limit

        return {"name": name, "notes": notes_string, "remindsMeOf": reminds_string}

    except RuntimeError as e:
        # algolia_search raises RuntimeError when the key was rejected AND the
        # automatic refresh failed. We report it as a distinct error (instead of
        # the vague "unavailable") so you know exactly what to fix: replace the key.
        print("ALGOLIA KEY PROBLEM:", e)
        return {"name": name, "error": "algolia key expired and auto-refresh failed"}

    except Exception as e:
        # Safety net for anything unexpected (network failure, Fragrantica changing
        # its page layout, etc.). Print the error for debugging, but still return a
        # valid response so the server keeps running.
        print(e)
        return {"name": name, "notes": "unavailable", "remindsMeOf": "unavailable"}


# ---------------------------------------------------------------------------
# FLASK APP AND ROUTE
# ---------------------------------------------------------------------------
app = Flask(__name__)   # creates the web application object


@app.route("/notes", methods=["GET"])   # URL path this function answers, GET requests only
def get_notes():
    """
    Handles:  GET /notes?name=Sauvage
    The ESP32, a browser or curl can all call it.
    """
    # request.args holds the query-string values (the part after "?").
    # .get("name") returns the value, or None if "name" wasn't supplied.
    name = request.args.get("name")

    # No name (or an empty one): reject with HTTP 400 ("bad request").
    if not name:
        return jsonify({"error": "missing name"}), 400

    # Normalize the cache key: lowercase with no surrounding spaces, so
    # "Aventus", "aventus" and " AVENTUS " all share one cache entry.
    key = name.strip().lower()

    # Cache hit: return the stored result immediately with no network work.
    if key in cache:
        return jsonify(cache[key])

    # Cache miss: do the full lookup (can take 5-15 seconds the first time).
    result = scrap_notes(name)

    # Dead Algolia key: answer HTTP 503 ("service unavailable") so the caller sees
    # a clear failure, and do NOT cache it, so the next request tries again.
    if "error" in result:
        return jsonify(result), 503

    # Cache only real results. If we cached "unavailable" or "not found", a
    # temporary hiccup would be remembered until the server restarted.
    if result["notes"] not in ("unavailable", "not found"):
        cache[key] = result

    # jsonify turns the Python dictionary into a proper JSON HTTP response.
    return jsonify(result)


# This block runs only when the file is started directly ("python app.py"),
# not when it is imported by another file.
if __name__ == "__main__":
    # host="0.0.0.0" -> accept connections from other devices on the network
    #                   (needed so the ESP32 can reach this server).
    # port=5000      -> the port number in http://<ip>:5000
    # Debug mode is OFF. Turn it on (debug=True) while developing to get
    # auto-reload and detailed error pages, but never when others can reach it.
    app.run(host="0.0.0.0", port=5000)