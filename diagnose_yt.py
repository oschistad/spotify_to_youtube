#!/usr/bin/env python3
"""
Diagnose YouTube Music search failures.

search() does NOT require auth in ytmusicapi, so this compares an
unauthenticated client against your browser.json to isolate the cause of
empty-response (JSONDecodeError: Expecting value) errors.
"""

import os
import sys

from ytmusicapi import YTMusic


def try_search(label, ytmusic):
    print(f"\n[{label}] searching for 'Metallica' (artists)...")
    try:
        results = ytmusic.search("Metallica", filter="artists", limit=1)
        print(f"  OK — {len(results)} result(s)")
        if results:
            print(f"  first: {results[0].get('artist')} -> {results[0].get('browseId')}")
        return True
    except Exception as e:
        print(f"  FAILED — {type(e).__name__}: {e}")
        return False


def main():
    import ytmusicapi
    print(f"ytmusicapi version: {ytmusicapi.__version__}")

    # 1. Unauthenticated — search should still work
    try_search("no auth", YTMusic())

    # 2. With browser.json
    browser_json = os.path.join(os.getcwd(), "browser.json")
    if os.path.exists(browser_json):
        try_search("browser.json", YTMusic(browser_json))
    else:
        print("\n[browser.json] not found, skipping")

    print(
        "\nInterpretation:\n"
        "  - both OK            -> search works; the bug was elsewhere\n"
        "  - no-auth OK, auth bad -> browser.json is the problem (re-run ytmusicapi browser)\n"
        "  - both fail          -> network/region/version issue, not your auth\n"
    )


if __name__ == "__main__":
    main()
