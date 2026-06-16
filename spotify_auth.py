#!/usr/bin/env python3
"""
Spotify OAuth handler with a local HTTP callback server.

Uses http://127.0.0.1 (loopback IP) as the redirect URI — Spotify accepts
this without requiring HTTPS. Falls back to manual URL paste over SSH.
"""

import http.server
import os
import threading
import urllib.parse
import webbrowser

import requests


REDIRECT_PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"

_SUCCESS_HTML = b"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h2>Authentication successful!</h2>
<p>You can close this tab and return to the terminal.</p>
</body></html>"""

_ERROR_HTML = b"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h2>Authentication failed</h2>
<p>Please check the terminal for details.</p>
</body></html>"""


def _run_callback_server(code_holder: dict):
    """Start a one-shot HTTP server on 127.0.0.1 that captures the OAuth code."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = dict(urllib.parse.parse_qsl(parsed.query))

            if "code" in params:
                code_holder["code"] = params["code"]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(_SUCCESS_HTML)
            else:
                code_holder["error"] = params.get("error", "unknown")
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(_ERROR_HTML)

            threading.Thread(target=self.server.shutdown).start()

    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    server.serve_forever()


def _exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(client_id, client_secret),
    )
    resp.raise_for_status()
    return resp.json()


def _manual_fallback(auth_url: str) -> str:
    """Ask the user to paste the redirect URL from their browser after auth."""
    print()
    print("Open this URL in your browser to authorise Spotify:")
    print()
    print(f"  {auth_url}")
    print()
    print("After logging in, your browser will show a 'connection refused' page —")
    print("that's fine. Copy the full URL from the address bar and paste it below.")
    print()
    redirected = input("Paste redirect URL: ").strip()
    parsed = urllib.parse.urlparse(redirected)
    params = dict(urllib.parse.parse_qsl(parsed.query))
    if "error" in params:
        raise RuntimeError(f"Spotify auth denied: {params['error']}")
    if "code" not in params:
        raise RuntimeError("No code found in the pasted URL.")
    return params["code"]


def _is_ssh_session() -> bool:
    return bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"))


def get_spotify_token(client_id: str, client_secret: str, scope: str) -> dict:
    """
    Run Spotify Authorization Code flow.
    Uses a local HTTP server on 127.0.0.1 when running locally.
    Falls back to manual URL paste over SSH.
    """
    import secrets

    state = secrets.token_urlsafe(16)
    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&scope={urllib.parse.quote(scope)}"
        f"&state={state}"
    )

    if _is_ssh_session():
        code = _manual_fallback(auth_url)
        return _exchange_code(client_id, client_secret, code)

    code_holder: dict = {}
    server_thread = threading.Thread(
        target=_run_callback_server, args=(code_holder,), daemon=True
    )
    server_thread.start()

    print("Opening Spotify login in your browser...")
    webbrowser.open(auth_url)

    server_thread.join(timeout=120)

    if "error" in code_holder:
        raise RuntimeError(f"Spotify auth denied: {code_holder['error']}")

    code = code_holder.get("code") or _manual_fallback(auth_url)
    return _exchange_code(client_id, client_secret, code)
