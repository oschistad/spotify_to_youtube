#!/usr/bin/env python3
"""
Migrate followed artists from Spotify to YouTube Music subscriptions.
"""

import argparse
import os
import sys
import time

import requests
import spotipy
from ytmusicapi import YTMusic

from spotify_auth import get_spotify_token, REDIRECT_URI


def load_env():
    """Load .env file if present."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not installed; rely on environment variables directly


CACHE_PATH = ".spotify_token.json"


def get_spotify_client():
    """Create and return an authenticated Spotify client."""
    import json
    import time

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set.")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    scope = "user-follow-read"
    token = None

    # Load cached token
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            token = json.load(f)

    # Refresh if expired
    if token and token.get("expires_at", 0) < time.time() + 60:
        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "refresh_token", "refresh_token": token["refresh_token"]},
            auth=(client_id, client_secret),
        )
        if resp.ok:
            refreshed = resp.json()
            token["access_token"] = refreshed["access_token"]
            token["expires_at"] = time.time() + refreshed["expires_in"]
            if "refresh_token" in refreshed:
                token["refresh_token"] = refreshed["refresh_token"]
            with open(CACHE_PATH, "w") as f:
                json.dump(token, f)
        else:
            token = None  # force re-auth

    # Full auth flow if no valid token
    if not token:
        import time as _time
        token = get_spotify_token(client_id, client_secret, scope)
        token["expires_at"] = _time.time() + token.get("expires_in", 3600)
        with open(CACHE_PATH, "w") as f:
            json.dump(token, f)

    return spotipy.Spotify(auth=token["access_token"])


def get_ytmusic_client():
    """Create and return an authenticated YouTube Music client."""
    browser_json = os.path.join(os.getcwd(), "browser.json")
    if not os.path.exists(browser_json):
        print("ERROR: browser.json not found in the current directory.")
        print("Run 'uv run ytmusicapi browser' to generate it, then try again.")
        sys.exit(1)
    return YTMusic(browser_json)


def fetch_spotify_followed_artists(sp, limit=None):
    """Fetch all followed artists from Spotify, handling pagination."""
    artists = []
    after = None
    batch_size = 50  # Spotify max per request

    print("Fetching followed artists from Spotify...")

    while True:
        kwargs = {"limit": batch_size}
        if after:
            kwargs["after"] = after

        result = sp.current_user_followed_artists(**kwargs)
        items = result["artists"]["items"]
        artists.extend(items)

        print(f"  Fetched {len(artists)} artists so far...")

        # Check if there are more pages
        cursor = result["artists"].get("cursors")
        next_after = cursor.get("after") if cursor else None

        if not next_after or not result["artists"].get("next"):
            break

        after = next_after

        if limit and len(artists) >= limit:
            break

    if limit:
        artists = artists[:limit]

    print(f"Total followed artists fetched: {len(artists)}\n")
    return artists


def find_youtube_artist(ytmusic, artist_name):
    """
    Search YouTube Music for an artist.
    Returns (channel_id, matched_name) or (None, None) if not found.
    Prefers exact name match; falls back to first result.
    """
    try:
        results = ytmusic.search(artist_name, filter="artists")
    except Exception as e:
        msg = str(e)
        hint = " (browser.json may be expired — re-run 'uv run ytmusicapi browser')" if "Expecting value" in msg else ""
        print(f"    WARNING: Search failed for '{artist_name}': {type(e).__name__}: {msg}{hint}")
        return None, None

    if not results:
        return None, None

    # Prefer exact (case-insensitive) name match
    for result in results:
        name = result.get("artist") or result.get("title") or ""
        if name.lower() == artist_name.lower():
            channel_id = result.get("browseId")
            return channel_id, name

    # Fall back to first result
    first = results[0]
    name = first.get("artist") or first.get("title") or ""
    channel_id = first.get("browseId")
    return channel_id, name


def migrate(dry_run=False, limit=None):
    load_env()

    sp = get_spotify_client()
    ytmusic = get_ytmusic_client()

    artists = fetch_spotify_followed_artists(sp, limit=limit)

    matched = []
    not_found = []
    subscribed = []
    failed_subscribe = []

    for i, artist in enumerate(artists, start=1):
        name = artist["name"]
        print(f"[{i}/{len(artists)}] Looking up: {name}")

        channel_id, matched_name = find_youtube_artist(ytmusic, name)
        time.sleep(0.5)

        if not channel_id:
            print(f"    NOT FOUND on YouTube Music")
            not_found.append(name)
            continue

        exact = matched_name.lower() == name.lower() if matched_name else False
        match_label = "exact match" if exact else f"best match: '{matched_name}'"
        print(f"    Found ({match_label}): {channel_id}")
        matched.append((name, matched_name, channel_id))

        if dry_run:
            print(f"    [DRY RUN] Would subscribe to {matched_name}")
        else:
            try:
                ytmusic.subscribe_artists([channel_id])
                print(f"    Subscribed!")
                subscribed.append((name, matched_name))
            except Exception as e:
                print(f"    ERROR subscribing: {e}")
                failed_subscribe.append((name, str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total artists processed : {len(artists)}")
    print(f"Matched on YouTube Music: {len(matched)}")
    print(f"Not found               : {len(not_found)}")

    if dry_run:
        print(f"[DRY RUN] Would have subscribed to {len(matched)} artists")
    else:
        print(f"Successfully subscribed : {len(subscribed)}")
        print(f"Failed to subscribe    : {len(failed_subscribe)}")

    if not_found:
        print("\nArtists NOT found on YouTube Music:")
        for name in not_found:
            print(f"  - {name}")

    if failed_subscribe:
        print("\nArtists found but subscription FAILED:")
        for name, err in failed_subscribe:
            print(f"  - {name}: {err}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Spotify followed artists to YouTube Music subscriptions."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Find matches but do not subscribe on YouTube Music.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        default=None,
        help="Only process the first N artists (useful for testing).",
    )
    args = parser.parse_args()

    migrate(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
