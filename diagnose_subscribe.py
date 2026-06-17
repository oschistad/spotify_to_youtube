#!/usr/bin/env python3
"""
Diagnose the empty-response JSONDecodeError on subscribe_artists.

Reuses the real YTMusic client's headers/cookies/context so the request is
an exact reproduction of what subscribe_artists() sends, but inspects the
raw HTTP response (status code, headers, body) before any JSON parsing —
ytmusicapi's own json.loads(response.text) call hides this on empty bodies.

Usage: uv run python diagnose_subscribe.py <channelId>
"""

import json
import os
import sys

from ytmusicapi import YTMusic
from ytmusicapi.constants import YTM_BASE_API


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python diagnose_subscribe.py <channelId>")
        sys.exit(1)
    channel_id = sys.argv[1]

    browser_json = os.path.join(os.getcwd(), "browser.json")
    if not os.path.exists(browser_json):
        print("ERROR: browser.json not found.")
        sys.exit(1)

    brand_account_id = os.environ.get("YT_BRAND_ACCOUNT_ID")
    yt = YTMusic(browser_json, user=brand_account_id)

    body = {"channelIds": [channel_id]}
    body.update(yt.context)

    url = YTM_BASE_API + "subscription/subscribe" + yt.params
    print(f"POST {url}")
    print(f"user param (brand account): {brand_account_id!r}")
    print(f"request body: {json.dumps(body)[:300]}")
    print()

    resp = yt._session.post(
        url,
        json=body,
        headers=yt.headers,
        proxies=yt.proxies,
        cookies=yt.cookies,
    )

    print(f"status_code: {resp.status_code}")
    print(f"response headers: {dict(resp.headers)}")
    print(f"response body (raw): {resp.text!r}")
    print(f"response body length: {len(resp.text)}")

    print()
    if resp.status_code in (200, 204) :
        print("=> Looks like SUCCESS despite the empty body. ytmusicapi's")
        print("   json.loads() call crashes on empty bodies regardless of")
        print("   status code, so subscribe_artists() misreports this as a")
        print("   failure even when YouTube accepted the subscription.")
    else:
        print(f"=> Real failure: HTTP {resp.status_code} with no JSON error body.")


if __name__ == "__main__":
    main()
